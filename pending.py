"""Warteschlange für Einträge, deren Schätzung nicht sofort klappt.

Ein neuer Eintrag landet zuerst in pending_entries und wird sofort in einem
eigenen Thread geschätzt. Die Anfrage wartet darauf nur WAIT_SECONDS: kommt
die Schätzung rechtzeitig, sieht die Person keinen Unterschied zu vorher.
Dauert sie länger oder ist Gemini ausgelastet, antwortet die App trotzdem –
der Eintrag bleibt in der Warteschlange und ein Hintergrund-Thread trägt ihn
nach, sobald die KI wieder antwortet. Datum und Uhrzeit sind die vom Moment
des Eintragens, nicht die der späteren Schätzung.

Die Zeilen liegen in SQLite und überleben damit auch einen Neustart des
Containers. Wer eine Zeile bearbeitet, markiert sie mit claimed_at; das
verhindert doppelte Schätzungen, auch falls einmal mehrere Gunicorn-Worker
laufen.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone

import ai
import db
from timeutil import utc_now_iso

log = logging.getLogger("kalorien.pending")

# So lange wartet POST /api/entries auf die Schätzung, bevor es den Eintrag
# als "wird nachgetragen" zurückmeldet. Eine normale Schätzung braucht wenige
# Sekunden; länger will niemand vor dem Knopf stehen.
WAIT_SECONDS = 15.0

# Eine Schätzung kann intern bis zu ai.TOTAL_DEADLINE (50 s) dauern. Ist ein
# Anspruch deutlich älter, ist der bearbeitende Prozess gestorben.
CLAIM_STALE_SECONDS = 120

# Wartezeit vor dem nächsten Versuch: 1, 2, 4, 8, dann alle 15 Minuten.
BACKOFF_FIRST = 60
BACKOFF_MAX = 15 * 60
# Danach wird aufgegeben und die Person entscheidet (nochmal / löschen). Ein
# ganzer Tag deckt auch ein ausgeschöpftes Tageslimit im Free Tier ab.
GIVE_UP_AFTER = timedelta(hours=24)

POLL_SECONDS = 10.0

_wake = threading.Event()
_started = False
_start_lock = threading.Lock()


def _iso(dt: datetime) -> str:
    # Dasselbe Format wie utc_now_iso(), damit Textvergleiche in SQL stimmen.
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pending_json(row) -> dict:
    return {
        "id": row["id"],
        "date": row["entry_date"],
        "time": row["entry_time"],
        "desc": row["desc"],
        "status": row["status"],
        "error": row["last_error"],
        "attempts": row["attempts"],
    }


def enqueue(conn, user_id: int, entry_date: str, entry_time: str,
            description: str, direction: str) -> int:
    """Legt einen wartenden Eintrag an, bereits beansprucht vom Aufrufer."""
    now = utc_now_iso()
    cur = conn.execute(
        'INSERT INTO pending_entries (user_id, entry_date, entry_time, "desc", '
        "direction, next_attempt_at, claimed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, entry_date, entry_time, description, direction, now, now, now),
    )
    conn.commit()
    return cur.lastrowid


def _claim(conn, pending_id: int) -> bool:
    stale = _iso(_now() - timedelta(seconds=CLAIM_STALE_SECONDS))
    cur = conn.execute(
        "UPDATE pending_entries SET claimed_at = ? "
        "WHERE id = ? AND status = 'waiting' AND (claimed_at IS NULL OR claimed_at < ?)",
        (utc_now_iso(), pending_id, stale),
    )
    conn.commit()
    return cur.rowcount == 1


def process(pending_id: int, claimed: bool = False) -> dict:
    """Schätzt einen wartenden Eintrag.

    Rückgabe {"status": ...}:
      "done"    – Eintrag angelegt, "entry_id" zeigt darauf
      "retry"   – vorübergehender Fehler, neuer Versuch ist geplant
      "failed"  – dauerhafter Fehler oder aufgegeben, "error" nennt den Grund
      "gone"    – Zeile existiert nicht mehr oder ist schon in Arbeit
    """
    conn = db.connect()
    try:
        if not claimed and not _claim(conn, pending_id):
            return {"status": "gone"}
        row = conn.execute(
            "SELECT * FROM pending_entries WHERE id = ?", (pending_id,)
        ).fetchone()
        if not row:
            return {"status": "gone"}

        try:
            estimate = ai.estimate_meal(row["desc"], row["direction"])
        except ai.AIError as exc:
            return _record_failure(conn, row, exc)
        except Exception as exc:  # darf den Worker nicht beenden
            log.exception("Unerwarteter Fehler beim Nachtragen von %s", pending_id)
            return _record_failure(conn, row, ai.AIError(
                "Die KI-Anfrage ist fehlgeschlagen.", retryable=True))

        # Erst die Warteschlangen-Zeile entfernen und nur dann eintragen: hat
        # die Person den Eintrag inzwischen gelöscht, bleibt es dabei.
        with conn:
            cur = conn.execute("DELETE FROM pending_entries WHERE id = ?", (pending_id,))
            if cur.rowcount != 1:
                return {"status": "gone"}
            cur = conn.execute(
                'INSERT INTO entries (user_id, entry_date, entry_time, "desc", kcal, '
                "protein, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["user_id"], row["entry_date"], row["entry_time"],
                 estimate["normalized"], estimate["kcal"], estimate["protein"],
                 utc_now_iso()),
            )
        if row["attempts"]:
            log.info("Eintrag %s nach %d Fehlversuch(en) nachgetragen",
                     pending_id, row["attempts"])
        return {"status": "done", "entry_id": cur.lastrowid}
    finally:
        conn.close()


def _record_failure(conn, row, exc: ai.AIError) -> dict:
    attempts = row["attempts"] + 1
    created = datetime.fromisoformat(row["created_at"])
    give_up = not exc.retryable or _now() - created > GIVE_UP_AFTER
    if give_up:
        conn.execute(
            "UPDATE pending_entries SET status = 'failed', attempts = ?, "
            "last_error = ?, claimed_at = NULL WHERE id = ?",
            (attempts, str(exc), row["id"]),
        )
        conn.commit()
        log.warning("Eintrag %s aufgegeben: %s", row["id"], exc)
        return {"status": "failed", "error": str(exc)}
    delay = min(BACKOFF_FIRST * 2 ** (attempts - 1), BACKOFF_MAX)
    conn.execute(
        "UPDATE pending_entries SET attempts = ?, last_error = ?, "
        "next_attempt_at = ?, claimed_at = NULL WHERE id = ?",
        (attempts, str(exc), _iso(_now() + timedelta(seconds=delay)), row["id"]),
    )
    conn.commit()
    log.info("Eintrag %s: Versuch %d fehlgeschlagen (%s), nächster in %d s",
             row["id"], attempts, exc, delay)
    return {"status": "retry", "error": str(exc)}


def estimate_now(pending_id: int) -> dict | None:
    """Startet die Schätzung sofort und wartet höchstens WAIT_SECONDS.

    None heißt: läuft noch, das Ergebnis kommt im Hintergrund.
    """
    result: dict = {}

    def run():
        result.update(process(pending_id, claimed=True))

    worker = threading.Thread(target=run, name=f"estimate-{pending_id}", daemon=True)
    worker.start()
    worker.join(WAIT_SECONDS)
    return result or None


def retry(conn, user_id: int, pending_id: int) -> bool:
    """Schiebt einen aufgegebenen oder wartenden Eintrag nach vorn.

    Bei einem aufgegebenen Eintrag beginnt die 24-Stunden-Frist neu – sonst
    würde "Nochmal versuchen" nach einem Tag sofort wieder aufgeben.
    """
    cur = conn.execute(
        "UPDATE pending_entries SET status = 'waiting', next_attempt_at = ?, "
        "created_at = CASE WHEN status = 'failed' THEN ? ELSE created_at END "
        "WHERE id = ? AND user_id = ?",
        (utc_now_iso(), utc_now_iso(), pending_id, user_id),
    )
    conn.commit()
    if cur.rowcount:
        _wake.set()
    return cur.rowcount == 1


def _due_ids() -> list[int]:
    conn = db.connect()
    try:
        stale = _iso(_now() - timedelta(seconds=CLAIM_STALE_SECONDS))
        rows = conn.execute(
            "SELECT id FROM pending_entries WHERE status = 'waiting' "
            "AND next_attempt_at <= ? AND (claimed_at IS NULL OR claimed_at < ?) "
            "ORDER BY next_attempt_at, id LIMIT 10",
            (utc_now_iso(), stale),
        ).fetchall()
        return [r["id"] for r in rows]
    finally:
        conn.close()


def _loop() -> None:
    while True:
        try:
            for pending_id in _due_ids():
                process(pending_id)
        except Exception:
            log.exception("Fehler in der Warteschlange für Einträge")
        _wake.wait(POLL_SECONDS)
        _wake.clear()


def start_worker() -> None:
    """Startet den Hintergrund-Thread einmal pro Prozess."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="pending-entries", daemon=True).start()
