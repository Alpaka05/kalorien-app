"""SQLite-Zugriff, Schema und Migrationen.

Die Datenbank liegt unter data/kalorien.db und ist über das Docker-Volume
persistent. Alle Schema-Änderungen hier sind idempotent, damit die App mit
mehreren Gunicorn-Workern und über Updates hinweg sauber startet.
"""

import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH") or os.path.join(APP_DIR, "data", "kalorien.db")

TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    kcal_goal       REAL,
    protein_goal    REAL,
    -- Stunde, ab der ein neuer Tag zählt. 0 = Mitternacht, 4 = alles vor
    -- 04:00 gehört noch zum Vortag (für späte Esser).
    day_start_hour  INTEGER NOT NULL DEFAULT 0,
    -- 'gain' oder 'lose'. Bestimmt, ob kcal_goal als Untergrenze gelesen wird,
    -- die erreicht werden soll, oder als Obergrenze, unter der man bleiben
    -- will. 'gain' ist der Standard, weil die App so angefangen hat.
    goal_direction  TEXT NOT NULL DEFAULT 'gain',
    -- 1 = Schnellwahl-Chips unter dem Eingabefeld zeigen, 0 = ausblenden.
    show_presets    INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    entry_date  TEXT NOT NULL,
    entry_time  TEXT NOT NULL,
    "desc"      TEXT NOT NULL,
    kcal        REAL NOT NULL,
    protein     REAL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    weigh_date  TEXT NOT NULL,
    kg          REAL NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (user_id, weigh_date)
);

CREATE TABLE IF NOT EXISTS login_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL,
    code_hash   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    consumed_at TEXT,
    request_ip  TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

-- Verlauf der Tagesziele und der Zielrichtung. Eine Zeile gilt ab valid_from (logischer Tag der
-- Person) bis zur nächsten Zeile. So bewertet eine Zieländerung nur Tage ab
-- dem Tag der Änderung neu, ältere Tage behalten das Ziel, das damals galt.
-- users.kcal_goal/protein_goal/goal_direction bleiben der aktuelle Stand.
CREATE TABLE IF NOT EXISTS goal_history (
    user_id       INTEGER NOT NULL,
    valid_from    TEXT NOT NULL,
    kcal_goal     REAL,
    protein_goal  REAL,
    goal_direction TEXT NOT NULL DEFAULT 'gain',
    created_at    TEXT NOT NULL,
    PRIMARY KEY (user_id, valid_from)
);

-- Einträge, deren Schätzung noch aussteht, weil Gemini ausgelastet war oder
-- zu lange brauchte. pending.py arbeitet sie im Hintergrund ab und legt dann
-- den eigentlichen Eintrag mit dem ursprünglichen Datum und der ursprünglichen
-- Uhrzeit an. Eine eigene Tabelle statt einer Spalte in entries, damit
-- entries.kcal nie leer ist und keine Summe die Wartenden mitzählt.
CREATE TABLE IF NOT EXISTS pending_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    entry_date      TEXT NOT NULL,
    entry_time      TEXT NOT NULL,
    "desc"          TEXT NOT NULL,
    -- Zielrichtung beim Eintragen: sie entscheidet, in welche Richtung die
    -- Schätzung bei Unsicherheit ausweicht.
    direction       TEXT NOT NULL DEFAULT 'gain',
    -- 'waiting' = wird (erneut) versucht, 'failed' = aufgegeben, wartet auf
    -- die Person (nochmal versuchen oder löschen).
    status          TEXT NOT NULL DEFAULT 'waiting',
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    next_attempt_at TEXT NOT NULL,
    -- Gesetzt, solange ein Thread die Zeile bearbeitet. Ein alter Wert heißt:
    -- der Prozess ist dabei gestorben, die Zeile darf neu vergeben werden.
    claimed_at      TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coach_cache (
    user_id     INTEGER NOT NULL,
    day         TEXT NOT NULL,
    inputs_hash TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);
"""

# Indizes erst nach den Migrationen anlegen: auf einer Datenbank aus der
# Single-User-Version existiert entries.user_id beim ersten Start noch nicht.
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_entries_user_date ON entries (user_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_weights_user_date ON weights (user_id, weigh_date);
CREATE INDEX IF NOT EXISTS idx_sessions_user      ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_login_codes_email  ON login_codes (email, created_at);
CREATE INDEX IF NOT EXISTS idx_pending_due        ON pending_entries (status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_pending_user_date  ON pending_entries (user_id, entry_date);
"""


# Beginn des Zielverlaufs für Konten, die schon vor dem Verlauf existierten.
GOAL_HISTORY_START = "0000-01-01"


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # WAL, damit gleichzeitige Lese- und Schreibzugriffe der Gunicorn-Worker
    # sich nicht blockieren; busy_timeout fängt kurze Schreibkollisionen ab.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _fix_legacy_times(conn: sqlite3.Connection) -> None:
    """Rechnet Einträge aus der Single-User-Version auf lokale Zeit um.

    Damals wurden Datum und Uhrzeit ohne Zeitzone geschrieben, in einem
    Container, der in UTC läuft. Die Anzeige lag dadurch 1–2 Stunden zurück,
    und alles zwischen lokal 00:00 und 02:00 landete am Vortag. Ohne diese
    Korrektur würde der Altbestand den Fehler dauerhaft behalten.
    """
    from datetime import datetime, timezone

    from timeutil import TZ

    rows = conn.execute("SELECT id, entry_date, entry_time FROM entries").fetchall()
    corrected = []
    for row in rows:
        try:
            as_utc = datetime.fromisoformat(
                f"{row['entry_date']} {row['entry_time']}"
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue  # unerwartetes Format lieber unangetastet lassen
        local = as_utc.astimezone(TZ)
        corrected.append(
            (local.date().isoformat(), local.strftime("%H:%M"), row["id"])
        )
    if corrected:
        conn.executemany(
            "UPDATE entries SET entry_date = ?, entry_time = ? WHERE id = ?",
            corrected,
        )


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(TABLES)
        # Migration von der Single-User-Version: entries hatte weder user_id
        # noch protein.
        entry_cols = _columns(conn, "entries")
        if "user_id" not in entry_cols:
            # Diese Bedingung trifft genau einmal pro Datenbank zu und ist
            # damit der richtige Ort für die einmalige Zeitkorrektur.
            _fix_legacy_times(conn)
            conn.execute("ALTER TABLE entries ADD COLUMN user_id INTEGER")
        if "protein" not in entry_cols:
            conn.execute("ALTER TABLE entries ADD COLUMN protein REAL")
        user_cols = _columns(conn, "users")
        if "day_start_hour" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN day_start_hour INTEGER NOT NULL DEFAULT 0"
            )
        if "goal_direction" not in user_cols:
            # Bestehende Konten sind alle zum Zunehmen angelegt worden, der
            # Standard hält deren Auswertung also unverändert.
            conn.execute(
                "ALTER TABLE users ADD COLUMN goal_direction TEXT NOT NULL DEFAULT 'gain'"
            )
        # Konten ohne Zielverlauf: das heute gespeicherte Ziel ist das Einzige,
        # was über früher bekannt ist, also gilt es für den gesamten Altbestand.
        # "0000-01-01" liegt vor jedem echten Tag.
        if "goal_direction" not in _columns(conn, "goal_history"):
            # Frühe Fassung des Verlaufs ohne Zielrichtung: die bis dahin
            # gespeicherte Richtung gilt für alle vorhandenen Zeilen.
            conn.execute(
                "ALTER TABLE goal_history "
                "ADD COLUMN goal_direction TEXT NOT NULL DEFAULT 'gain'"
            )
            conn.execute(
                "UPDATE goal_history SET goal_direction = COALESCE("
                "(SELECT goal_direction FROM users WHERE users.id = goal_history.user_id), "
                "'gain')"
            )
        conn.execute(
            "INSERT INTO goal_history "
            "(user_id, valid_from, kcal_goal, protein_goal, goal_direction, created_at) "
            "SELECT id, ?, kcal_goal, protein_goal, goal_direction, created_at FROM users "
            "WHERE id NOT IN (SELECT user_id FROM goal_history)",
            (GOAL_HISTORY_START,),
        )
        if "show_presets" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN show_presets INTEGER NOT NULL DEFAULT 1"
            )
        conn.commit()
        conn.executescript(INDEXES)
        conn.commit()
    finally:
        conn.close()


def adopt_orphan_entries(conn: sqlite3.Connection, user_id: int) -> int:
    """Weist Einträge ohne Besitzer dem ersten registrierten Konto zu.

    Vor dem Account-System gehörten alle Einträge derselben Person. Damit deren
    Verlauf beim Umstieg nicht verloren geht, übernimmt sie der erste Account.
    """
    user_count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count != 1:
        return 0
    cur = conn.execute(
        "UPDATE entries SET user_id = ? WHERE user_id IS NULL", (user_id,)
    )
    return cur.rowcount or 0


def goals_by_date(conn: sqlite3.Connection, user_id: int, dates: list[str]) -> dict:
    """Ziel, das an jedem der Tage galt.

    Liefert {datum: {"kcal_goal", "protein_goal", "goal_direction"}}. Für Tage
    vor dem ersten Eintrag im Verlauf gibt es kein Ziel; die Richtung ist dann
    der Standard "gain".
    """
    if not dates:
        return {}
    rows = conn.execute(
        "SELECT valid_from, kcal_goal, protein_goal, goal_direction FROM goal_history "
        "WHERE user_id = ? AND valid_from <= ? ORDER BY valid_from ASC",
        (user_id, max(dates)),
    ).fetchall()
    result = {}
    for day in dates:
        current = {"kcal_goal": None, "protein_goal": None, "goal_direction": "gain"}
        for row in rows:
            if row["valid_from"] > day:
                break
            current = {
                "kcal_goal": row["kcal_goal"],
                "protein_goal": row["protein_goal"],
                "goal_direction": (
                    row["goal_direction"] if row["goal_direction"] in ("gain", "lose") else "gain"
                ),
            }
        result[day] = current
    return result
