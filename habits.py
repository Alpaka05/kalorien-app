"""Ziele ("habits"): Zeiträume, Serien und Meilensteine.

Ein Ziel heißt: `target`-mal pro Tag, Woche oder Monat. Ein Zeitraum ist
geschafft, wenn genug Einträge darin liegen. Die Serie zählt die geschafften
Zeiträume am Stück bis heute. Der laufende Zeitraum bricht sie nie – er zählt
mit, sobald er geschafft ist, und wird erst zum Bruch, wenn er vorbei ist.

Bei Wochen- und Monatszielen zählt jeder Tag höchstens einmal (die API lässt
keinen zweiten Eintrag am selben Tag zu, und gezählt werden Tage, nicht
Zeilen). Tagesziele zählen jeden Eintrag, höchstens bis zum Ziel.

Hier steht nur Rechnung ohne Datenbank und ohne Flask, damit sie sich allein
prüfen lässt.
"""

from collections import Counter
from datetime import date, timedelta

PERIODS = ("day", "week", "month")

# Höchstwert für `target` je Zeitraum: öfter als einmal am Tag geht bei
# Wochen- und Monatszielen nicht.
MAX_TARGET = {"day": 10, "week": 7, "month": 31}

# Etappen der Serie. Nach der letzten geht es im selben Abstand weiter
# (365, 730, … Tage).
MILESTONES = {
    "day": (3, 7, 14, 30, 60, 100, 180, 365),
    "week": (4, 8, 12, 26, 52),
    "month": (3, 6, 12, 24),
}

# Gezeichnete Symbole, die ein Ziel tragen darf (Pfade in static/app.js).
ICONS = (
    "dumbbell", "leaf", "apple", "book", "drop", "moon",
    "heart", "bike", "sun", "glass", "music", "star",
)

MAX_HABITS = 30
TITLE_MAX = 60
# Wie viele vergangene Zeiträume die Übersicht als Kästchen zeigt.
RECENT_PERIODS = 7


def period_start(day: date, period: str) -> date:
    if period == "week":
        return day - timedelta(days=day.weekday())
    if period == "month":
        return day.replace(day=1)
    return day


def next_period_start(start: date, period: str) -> date:
    if period == "week":
        return start + timedelta(days=7)
    if period == "month":
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def period_end(start: date, period: str) -> date:
    """Letzter Tag des Zeitraums (einschließlich)."""
    return next_period_start(start, period) - timedelta(days=1)


def milestone_list(period: str, upto: int) -> list[int]:
    """Alle Etappen bis mindestens eine über `upto`."""
    marks = list(MILESTONES[period])
    step = marks[-1]
    while marks[-1] <= upto:
        marks.append(marks[-1] + step)
    return marks


def milestone_before(period: str, value: int) -> int:
    """Größte Etappe ≤ value, sonst 0."""
    return max((m for m in milestone_list(period, value) if m <= value), default=0)


def milestone_after(period: str, value: int) -> int:
    """Kleinste Etappe > value."""
    return min(m for m in milestone_list(period, value) if m > value)


def is_milestone(period: str, value: int) -> bool:
    return value > 0 and value in milestone_list(period, value)


def _count_per_period(dates: list[str], period: str, today: date) -> Counter:
    """Einträge je Zeitraumbeginn. Wochen und Monate zählen Tage, nicht Zeilen."""
    per_period: Counter = Counter()
    if period == "day":
        for iso in dates:
            day = date.fromisoformat(iso)
            if day <= today:
                per_period[day] += 1
    else:
        for iso in set(dates):
            day = date.fromisoformat(iso)
            if day <= today:
                per_period[period_start(day, period)] += 1
    return per_period


def stats(habit, dates: list[str], today_iso: str) -> dict:
    """Stand eines Ziels.

    `habit` braucht period, target und start_date; `dates` sind die logischen
    Tage aller Einträge (bei Tageszielen mehrfach, wenn mehrfach eingetragen).
    """
    period = habit["period"]
    target = int(habit["target"])
    today = date.fromisoformat(today_iso)
    per_period = _count_per_period(dates, period, today)

    # Nachgetragene Tage vor der Anlage verschieben den Beginn nach vorn –
    # sonst würden sie gezählt, aber die Zeiträume dazwischen nicht.
    first = date.fromisoformat(habit["start_date"])
    if dates:
        first = min(first, min(date.fromisoformat(d) for d in dates))
    first = min(first, today)

    current = period_start(today, period)
    met = []  # abgeschlossene Zeiträume, älteste zuerst
    start = period_start(first, period)
    while start < current:
        met.append(per_period.get(start, 0) >= target)
        start = next_period_start(start, period)

    count = per_period.get(current, 0)
    current_met = count >= target

    run = 0
    for flag in reversed(met):
        if not flag:
            break
        run += 1
    streak = run + (1 if current_met else 0)

    best = longest = 0
    for flag in met + ([True] if current_met else []):
        longest = longest + 1 if flag else 0
        best = max(best, longest)

    # Leiste bis zur nächsten Etappe. Der laufende Zeitraum zählt anteilig mit,
    # damit sie bei jedem Eintrag wächst. Ist gerade eine Etappe erreicht,
    # bleibt sie bis zum Ende des Zeitraums voll stehen.
    milestone_hit = current_met and is_milestone(period, streak)
    if milestone_hit:
        bar = {"from": milestone_before(period, streak - 1), "to": streak, "value": streak}
    else:
        value = streak + (0 if current_met else min(count / target, 1))
        bar = {
            "from": milestone_before(period, streak),
            "to": milestone_after(period, streak),
            "value": round(value, 3),
        }

    end = period_end(current, period)
    days_left = (end - today).days + 1
    risk = None
    if period != "day" and not current_met and run > 0:
        today_done = today_iso in dates
        open_days = days_left - (1 if today_done else 0)
        needed = target - count
        if needed > open_days:
            risk = "lost"
        elif needed == open_days:
            risk = "tight"

    recent = [None] * max(0, RECENT_PERIODS - len(met)) + met[-RECENT_PERIODS:]
    met_count = sum(met) + (1 if current_met else 0)
    return {
        "current": {
            "start": current.isoformat(),
            "end": end.isoformat(),
            "count": count,
            "met": current_met,
            "days_left": days_left,
        },
        "streak": streak,
        "run_before": run,
        "best": best,
        "bar": bar,
        "milestone_hit": milestone_hit,
        "risk": risk,
        "recent": recent,
        "totals": {
            "entries": len(dates),
            # Abgeschlossene Zeiträume plus der laufende, wenn er schon zählt.
            "periods": len(met) + (1 if current_met else 0),
            "met": met_count,
        },
    }


def met_periods(dates: list[str], habit, start_iso: str, end_iso: str) -> dict:
    """Welche Zeiträume zwischen zwei Tagen geschafft waren: {beginn: bool}."""
    period = habit["period"]
    target = int(habit["target"])
    end = date.fromisoformat(end_iso)
    per_period = _count_per_period(dates, period, end)
    result = {}
    start = period_start(date.fromisoformat(start_iso), period)
    while start <= end:
        result[start.isoformat()] = per_period.get(start, 0) >= target
        start = next_period_start(start, period)
    return result
