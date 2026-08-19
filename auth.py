"""Passwortloses Konto-System: E-Mail + Einmalcode.

Es gibt bewusst keine Passwörter. Wer sich anmelden will, bekommt einen
6-stelligen Code per Mail; ist die E-Mail noch unbekannt, wird beim ersten
erfolgreichen Code ein Konto angelegt. Codes und Session-Tokens liegen nur
als HMAC in der Datenbank.
"""

import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import db
from timeutil import utc_now_iso

CODE_TTL_MINUTES = 15
CODE_MAX_ATTEMPTS = 5
CODES_PER_EMAIL_PER_HOUR = 5
CODES_PER_IP_PER_HOUR = 20
SESSION_TTL_DAYS = 90
SESSION_RENEW_AFTER_DAYS = 7

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")


class AuthError(Exception):
    """Fehler, dessen Text der Nutzerin gezeigt werden darf."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# --------------------------------------------------------------------------
# Secret Key
# --------------------------------------------------------------------------

def _load_secret() -> bytes:
    # Ein selbst gesetzter SECRET_KEY wird auf volle Länge gehasht, damit auch
    # eine kurze Eingabe einen brauchbaren HMAC-Schlüssel ergibt und die App
    # nicht wegen der Schlüssellänge nicht mehr startet.
    env_secret = os.environ.get("SECRET_KEY", "").strip()
    if env_secret:
        return sha256(b"kalorien-app/v1:" + env_secret.encode("utf-8")).digest()

    secret = _read_or_create_secret()
    # Hier zählt die Länge: ein leerer Schlüssel aus einer beschädigten Datei
    # würde alle HMACs entwerten, ohne dass es auffällt.
    if len(secret) < 16:
        raise RuntimeError(
            "data/secret_key ist leer oder zu kurz. Datei löschen (alle "
            "Anmeldungen werden dadurch ungültig) oder SECRET_KEY in der .env setzen."
        )
    return secret


def _read_or_create_secret() -> bytes:
    # Ohne SECRET_KEY in der .env wird einmalig einer erzeugt und neben der
    # Datenbank abgelegt, damit Sessions einen Neustart überleben.
    path = os.path.join(os.path.dirname(db.DB_PATH), "secret_key")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, "r", encoding="ascii") as fh:
            existing = fh.read().strip()
        if len(existing) >= 16:
            return existing.encode("ascii")
    except (FileNotFoundError, UnicodeDecodeError):
        pass

    # Erst in eine temporäre Datei schreiben und dann umbenennen: ein
    # abgebrochener Start hinterlässt so keinen halben oder leeren Schlüssel,
    # mit dem alle Sessions still unsicher würden.
    generated = secrets.token_urlsafe(48)
    tmp_path = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp_path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(generated)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)
    return generated.encode("ascii")


_SECRET = _load_secret()


def _digest(*parts: str) -> str:
    msg = "\x00".join(parts).encode("utf-8")
    return hmac.new(_SECRET, msg, sha256).hexdigest()


# --------------------------------------------------------------------------
# Zeit-Helfer
# --------------------------------------------------------------------------

def _in(**delta) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(**delta))
        .replace(microsecond=0)
        .isoformat()
    )


def _expired(iso: str) -> bool:
    try:
        return datetime.fromisoformat(iso) <= datetime.now(timezone.utc)
    except ValueError:
        return True


# --------------------------------------------------------------------------
# E-Mail-Regeln
# --------------------------------------------------------------------------

def normalize_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise AuthError("Bitte gib eine gültige E-Mail-Adresse ein.")
    return email


def _allowlist() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _registration_open() -> bool | None:
    """True/False bei ausdrücklicher Angabe, sonst None (= Standardverhalten)."""
    raw = os.environ.get("REGISTRATION_OPEN", "").strip().lower()
    if not raw:
        return None
    return raw not in ("0", "false", "no")


def may_register(conn: sqlite3.Connection, email: str) -> bool:
    """Darf sich diese Adresse neu registrieren?

    Standard ist absichtlich restriktiv: Da die App typischerweise öffentlich
    erreichbar ist, darf sich ohne Konfiguration nur das erste Konto anlegen –
    das der Betreiberin. Weitere Personen werden per ALLOWED_EMAILS
    freigeschaltet oder mit REGISTRATION_OPEN=true generell zugelassen.
    """
    allow = _allowlist()
    if allow:
        return email in allow
    explicit = _registration_open()
    if explicit is not None:
        return explicit
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0


# --------------------------------------------------------------------------
# Login-Codes
# --------------------------------------------------------------------------

def create_login_code(conn: sqlite3.Connection, email: str, request_ip: str) -> str:
    """Legt einen neuen Einmalcode an und gibt ihn im Klartext zurück."""
    # Die Ratelimits werden VOR der Registrierungsprüfung ausgewertet und auch
    # bei abgelehnten Anfragen protokolliert. Sonst wäre die Prüfung ein
    # beliebig oft abfragbares Orakel dafür, welche Adressen ein Konto haben.
    hour_ago = _in(hours=-1)
    per_ip = conn.execute(
        "SELECT COUNT(*) AS n FROM login_codes WHERE request_ip = ? AND created_at > ?",
        (request_ip, hour_ago),
    ).fetchone()["n"]
    if per_ip >= CODES_PER_IP_PER_HOUR:
        raise AuthError("Zu viele Anfragen. Bitte versuch es später erneut.", 429)
    per_email = conn.execute(
        "SELECT COUNT(*) AS n FROM login_codes WHERE email = ? AND created_at > ?",
        (email, hour_ago),
    ).fetchone()["n"]
    if per_email >= CODES_PER_EMAIL_PER_HOUR:
        raise AuthError(
            "Zu viele Anfragen für diese Adresse. Bitte versuch es später erneut.",
            429,
        )

    known = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not known and not may_register(conn, email):
        # Fehlversuch mitzählen, damit die Abfrage nicht kostenlos ist.
        conn.execute(
            "INSERT INTO login_codes (email, code_hash, created_at, expires_at, "
            "consumed_at, request_ip) VALUES (?, ?, ?, ?, ?, ?)",
            (email, "rejected", utc_now_iso(), utc_now_iso(), utc_now_iso(), request_ip),
        )
        conn.commit()
        raise AuthError(
            "Für diese E-Mail-Adresse ist keine Registrierung freigegeben.", 403
        )

    code = f"{secrets.randbelow(1_000_000):06d}"
    # Ältere, noch offene Codes derselben Adresse entwerten.
    conn.execute(
        "UPDATE login_codes SET consumed_at = ? "
        "WHERE email = ? AND consumed_at IS NULL",
        (utc_now_iso(), email),
    )
    conn.execute(
        "INSERT INTO login_codes (email, code_hash, created_at, expires_at, request_ip) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            email,
            _digest("code", email, code),
            utc_now_iso(),
            _in(minutes=CODE_TTL_MINUTES),
            request_ip,
        ),
    )
    # Aufräumen: Codes, die älter als ein Tag sind, braucht niemand mehr.
    conn.execute("DELETE FROM login_codes WHERE created_at < ?", (_in(days=-1),))
    conn.commit()
    return code


def verify_login_code(conn: sqlite3.Connection, email: str, code: str) -> sqlite3.Row:
    """Prüft den Code und gibt den zugehörigen (ggf. neu erzeugten) Nutzer zurück."""
    code = (code or "").strip().replace(" ", "").replace("-", "")
    if not re.fullmatch(r"\d{6}", code):
        raise AuthError("Der Code besteht aus 6 Ziffern.")

    row = conn.execute(
        "SELECT * FROM login_codes WHERE email = ? AND consumed_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (email,),
    ).fetchone()
    if not row:
        raise AuthError("Kein offener Code. Fordere bitte einen neuen an.")
    if _expired(row["expires_at"]):
        raise AuthError("Der Code ist abgelaufen. Fordere bitte einen neuen an.")
    if row["attempts"] >= CODE_MAX_ATTEMPTS:
        conn.execute(
            "UPDATE login_codes SET consumed_at = ? WHERE id = ?",
            (utc_now_iso(), row["id"]),
        )
        conn.commit()
        raise AuthError("Zu viele Fehlversuche. Fordere bitte einen neuen Code an.")

    if not hmac.compare_digest(row["code_hash"], _digest("code", email, code)):
        conn.execute(
            "UPDATE login_codes SET attempts = attempts + 1 WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        raise AuthError("Der Code stimmt nicht.")

    conn.execute(
        "UPDATE login_codes SET consumed_at = ? WHERE id = ?",
        (utc_now_iso(), row["id"]),
    )

    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        if not may_register(conn, email):
            raise AuthError(
                "Für diese E-Mail-Adresse ist keine Registrierung freigegeben.", 403
            )
        cur = conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            (email, utc_now_iso()),
        )
        user_id = cur.lastrowid
        db.adopt_orphan_entries(conn, user_id)
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    conn.commit()
    return user


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = utc_now_iso()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen) "
        "VALUES (?, ?, ?, ?, ?)",
        (_digest("session", token), user_id, now, _in(days=SESSION_TTL_DAYS), now),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.commit()
    return token


def user_for_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    if not token:
        return None
    token_hash = _digest("session", token)
    row = conn.execute(
        "SELECT s.expires_at, u.* FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (token_hash,),
    ).fetchone()
    if not row:
        return None
    if _expired(row["expires_at"]):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
        return None
    # Session gleitend verlängern, aber nicht bei jedem Request schreiben.
    remaining = datetime.fromisoformat(row["expires_at"]) - datetime.now(timezone.utc)
    if remaining < timedelta(days=SESSION_TTL_DAYS - SESSION_RENEW_AFTER_DAYS):
        conn.execute(
            "UPDATE sessions SET expires_at = ?, last_seen = ? WHERE token_hash = ?",
            (_in(days=SESSION_TTL_DAYS), utc_now_iso(), token_hash),
        )
        conn.commit()
    return row


def destroy_session(conn: sqlite3.Connection, token: str) -> None:
    if not token:
        return
    conn.execute(
        "DELETE FROM sessions WHERE token_hash = ?", (_digest("session", token),)
    )
    conn.commit()
