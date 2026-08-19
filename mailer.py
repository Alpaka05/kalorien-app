"""Versand der Login-Codes per E-Mail.

Ist kein SMTP-Server konfiguriert, landet der Code im Container-Log
(`docker compose logs kalorien-tagebuch`). So kommt man auch ohne Mailserver
in die App, ohne dass der Code über die API nach außen geht.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("kalorien.mail")

def _port(raw: str, fallback: int) -> int:
    # Ein leeres oder falsch getipptes SMTP_PORT darf den Start nicht verhindern:
    # der Import passiert vor dem ersten Request, ein Fehler hier wäre eine
    # Crash-Schleife des Containers.
    text = (raw or "").strip()
    if not text:
        return fallback
    try:
        value = int(text)
    except ValueError:
        log.warning("SMTP_PORT=%r ist keine Zahl – nutze %d", raw, fallback)
        return fallback
    if not 1 <= value <= 65535:
        log.warning("SMTP_PORT=%r liegt außerhalb 1–65535 – nutze %d", raw, fallback)
        return fallback
    return value


SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = _port(os.environ.get("SMTP_PORT", ""), 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER
# starttls (Standard, Port 587) | ssl (Port 465) | none
SMTP_SECURITY = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
APP_NAME = os.environ.get("APP_NAME", "Kalorien-Tagebuch")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_login_code(email: str, code: str, minutes_valid: int) -> str:
    """Verschickt den Code. Gibt "smtp" oder "log" als Zustellweg zurück."""
    if not is_configured():
        log.warning(
            "SMTP nicht konfiguriert – Login-Code für %s lautet: %s (gültig %d Minuten)",
            email,
            code,
            minutes_valid,
        )
        return "log"

    msg = EmailMessage()
    msg["Subject"] = f"{APP_NAME}: Dein Anmeldecode {code}"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Dein Anmeldecode für {APP_NAME} lautet:\n\n"
        f"    {code}\n\n"
        f"Der Code ist {minutes_valid} Minuten gültig und kann nur einmal "
        f"verwendet werden.\n\n"
        f"Wenn du keine Anmeldung angefordert hast, kannst du diese Mail "
        f"einfach ignorieren."
    )

    try:
        if SMTP_SECURITY == "ssl":
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        with server:
            if SMTP_SECURITY == "starttls":
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        # Der Code selbst darf nie in einer API-Antwort landen, deshalb hier
        # nur loggen und dem Aufrufer den Fehlschlag melden.
        log.exception("Versand des Login-Codes an %s fehlgeschlagen", email)
        raise

    return "smtp"
