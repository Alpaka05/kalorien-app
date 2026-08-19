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
    """Kalendertag nach der Uhr (ohne persönlichen Tagesbeginn)."""
    return now_local().date().isoformat()


def logical_today(day_start_hour: int = 0) -> str:
    """Tag, dem "jetzt" zugerechnet wird.

    Bei einem Tagesbeginn von z. B. 4 gehört alles vor 04:00 noch zum Vortag –
    wer um 01:30 nachts isst, bucht es damit auf den Tag, an dem er wach
    geworden ist, statt auf den neuen Kalendertag.
    """
    now = now_local()
    if day_start_hour and now.hour < day_start_hour:
        return (now.date() - timedelta(days=1)).isoformat()
    return now.date().isoformat()


def logical_date_of(entry_date: str, entry_time: str, day_start_hour: int) -> str:
    """Rechnet einen gespeicherten Eintrag auf einen anderen Tagesbeginn um.

    Aus Datum und Uhrzeit lässt sich der echte Kalendertag eindeutig
    zurückrechnen, solange der alte Tagesbeginn bekannt ist. Damit ist die
    Umbuchung beim Ändern der Einstellung exakt und umkehrbar.
    """
    calendar = date.fromisoformat(entry_date)
    if day_start_hour and int(entry_time[:2]) < day_start_hour:
        return (calendar - timedelta(days=1)).isoformat()
    return calendar.isoformat()


def calendar_date_of(entry_date: str, entry_time: str, day_start_hour: int) -> str:
    """Echter Kalendertag eines Eintrags, der unter `day_start_hour` gebucht wurde."""
    calendar = date.fromisoformat(entry_date)
    if day_start_hour and int(entry_time[:2]) < day_start_hour:
        calendar += timedelta(days=1)
    return calendar.isoformat()


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
