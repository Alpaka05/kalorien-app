"""Ziele (habits): Rechnung in habits.py und die API darum."""

from datetime import date, timedelta

import habits


def habit(period="week", target=3, start="2026-10-01"):
    return {"period": period, "target": target, "start_date": start}


def days(start, *offsets):
    base = date.fromisoformat(start)
    return [(base + timedelta(days=o)).isoformat() for o in offsets]


# --- Rechnung ----------------------------------------------------------------

def test_month_boundaries():
    assert habits.next_period_start(date(2026, 1, 1), "month") == date(2026, 2, 1)
    assert habits.period_end(date(2026, 2, 1), "month") == date(2026, 2, 28)
    assert habits.period_end(date(2028, 2, 1), "month") == date(2028, 2, 29)
    assert habits.period_start(date(2026, 11, 8), "week") == date(2026, 11, 2)  # Montag


def test_weekly_streak_counts_days_not_rows():
    # Zwei Wochen mit je 3 Tagen, in der laufenden Woche erst 1.
    dates = days("2026-10-19", 0, 1, 2) + days("2026-10-26", 0, 2, 4) + ["2026-11-02"]
    s = habits.stats(habit(start="2026-10-19"), dates + ["2026-10-19"], "2026-11-04")
    assert s["streak"] == 2 and s["run_before"] == 2
    assert s["current"]["count"] == 1 and not s["current"]["met"]


def test_current_period_does_not_break_streak_until_over():
    dates = days("2026-10-26", 0, 1, 2)
    s = habits.stats(habit(start="2026-10-26"), dates, "2026-11-02")
    assert s["streak"] == 1
    s = habits.stats(habit(start="2026-10-26"), dates, "2026-11-09")
    assert s["streak"] == 0 and s["best"] == 1


def test_risk_when_week_can_no_longer_be_met():
    dates = days("2026-10-26", 0, 1, 2)
    # Sonntag der Folgewoche, noch nichts eingetragen: 3 nötig, 1 Tag übrig.
    s = habits.stats(habit(start="2026-10-26"), dates, "2026-11-08")
    assert s["risk"] == "lost"
    s = habits.stats(habit(start="2026-10-26"), dates + ["2026-11-06"], "2026-11-07")
    assert s["risk"] == "tight"


def test_milestones():
    assert habits.milestone_after("day", 0) == 3
    assert habits.milestone_after("day", 365) == 730
    assert habits.is_milestone("week", 4)
    assert not habits.is_milestone("week", 5)


def test_backfilled_days_before_start_count():
    s = habits.stats(habit("day", 1, start="2026-11-08"), days("2026-11-05", 0, 1, 2, 3), "2026-11-08")
    assert s["streak"] == 4


# --- API ---------------------------------------------------------------------

def create(client, **payload):
    payload = {"title": "Gym", "period": "week", "target": 3, "icon": "dumbbell", **payload}
    return client.post("/api/habits", json=payload)


def test_create_validates(client):
    assert create(client, title=" ").status_code == 400
    assert create(client, period="year").status_code == 400
    assert create(client, target=8).status_code == 400
    assert create(client, icon="rakete").status_code == 400
    assert create(client).status_code == 201


def test_weekly_goal_one_checkin_per_day(client):
    h = create(client).get_json()
    url = f"/api/habits/{h['id']}/checkins"
    assert client.post(url, json={}).status_code == 201
    assert client.post(url, json={}).status_code == 409
    assert client.post(url, json={"date": "2026-11-09"}).status_code == 400


def test_completing_week_reports_completed(client):
    h = create(client).get_json()
    url = f"/api/habits/{h['id']}/checkins"
    client.post(url, json={"date": "2026-11-02"})
    client.post(url, json={"date": "2026-11-04"})
    res = client.post(url, json={}).get_json()
    assert res["completed"] is True
    assert res["habit"]["streak"] == 1


def test_daily_goal_up_to_target(client):
    h = create(client, title="Wasser", period="day", target=2, icon="drop").get_json()
    url = f"/api/habits/{h['id']}/checkins"
    assert client.post(url, json={}).status_code == 201
    assert client.post(url, json={}).status_code == 201
    assert client.post(url, json={}).status_code == 409


def test_habits_are_private(make_client, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "ich@example.com,b@example.com")
    a = make_client("ich@example.com")
    b = make_client("b@example.com")
    h = create(a).get_json()
    assert b.get(f"/api/habits/{h['id']}").status_code == 404
    assert b.post(f"/api/habits/{h['id']}/checkins", json={}).status_code == 404
    assert b.delete(f"/api/habits/{h['id']}").status_code == 404


def test_day_start_moves_checkins_with_time(client, clock):
    h = create(client, period="day", target=1).get_json()
    clock.set(2026, 11, 8, 1, 30)
    client.post(f"/api/habits/{h['id']}/checkins", json={})
    client.patch("/api/me", json={"day_start_hour": 4})
    res = client.get(f"/api/habits/{h['id']}/checkins?date=2026-11-07").get_json()
    assert len(res["checkins"]) == 1
