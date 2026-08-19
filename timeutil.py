"""Zeitzonen-Helfer.

Der Container läuft in UTC. Alle nutzersichtbaren Datums- und Uhrzeitangaben
müssen aber in der lokalen Zeitzone stehen (Deutschland = UTC+1/+2), sonst
liegen die Zeiten der Mahlzeiten im Sommer 2 Stunden in der Vergangenheit.
"""

import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Europe/Berlin"


def _load_tz():
    for name in (os.environ.get("APP_TZ", "").strip(), DEFAULT_TZ):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            continue
    # Letzter Ausweg: ohne tzdata bleibt nur UTC. Zeiten sind dann verschoben,
    # aber die App startet trotzdem.
    return timezone.utc


TZ = _load_tz()


def now_local() -> datetime:
    """Aktueller Zeitpunkt in der App-Zeitzone (mit DST-Berücksichtigung)."""
    return datetime.now(TZ)


def today_iso() -> str:
    return now_local().date().isoformat()


def local_time_hhmm() -> str:
    return now_local().strftime("%H:%M")


def utc_now_iso() -> str:
    """UTC-Zeitstempel für interne created_at-Felder."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _shift(base, days: int):
    """Datum um `days` Tage zurück, ohne am Wertebereichsrand zu scheitern."""
    try:
        return base - timedelta(days=days)
    except OverflowError:
        return date.min


def day_offset_iso(days: int, end: str | None = None) -> str:
    """ISO-Datum `days` Tage vor `end` (Standard: heute)."""
    base = datetime.fromisoformat(end).date() if end else now_local().date()
    return _shift(base, days).isoformat()


def date_range_iso(days: int, end: str | None = None) -> list[str]:
    """Aufsteigende Liste von `days` ISO-Daten, die auf `end` endet."""
    base = datetime.fromisoformat(end).date() if end else now_local().date()
    return [_shift(base, i).isoformat() for i in range(days - 1, -1, -1)]
