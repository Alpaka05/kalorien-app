"""Ziel-Historie, Zielrichtung im Verlauf und die tägliche Einschätzung."""


def add(client, date, kcal):
    return client.post("/api/entries", json={"desc": "x", "date": date, "time": "12:00", "kcal": kcal})


def series(client, days=7, end="2026-11-08"):
    return {d["date"]: d for d in client.get(f"/api/summary?days={days}&end={end}").get_json()["series"]}


# --- Ziel-Historie -----------------------------------------------------------

def test_goal_change_applies_from_today_only(client, clock):
    clock.set(2026, 11, 5, 12, 0)
    client.patch("/api/me", json={"kcal_goal": 2500})
    clock.set(2026, 11, 8, 12, 0)
    client.patch("/api/me", json={"kcal_goal": 3000, "goal_direction": "lose"})
    s = series(client)
    assert s["2026-11-04"]["kcal_goal"] is None
    assert s["2026-11-05"]["kcal_goal"] == 2500
    assert s["2026-11-07"]["kcal_goal"] == 2500
    assert s["2026-11-07"]["goal_direction"] == "gain"
    assert s["2026-11-08"]["kcal_goal"] == 3000
    assert s["2026-11-08"]["goal_direction"] == "lose"


def test_several_changes_same_day_keep_last(client):
    client.patch("/api/me", json={"kcal_goal": 2000})
    client.patch("/api/me", json={"kcal_goal": 2200})
    assert series(client)["2026-11-08"]["kcal_goal"] == 2200


def test_reverting_to_yesterdays_goal_drops_todays_row(client, clock):
    import db

    clock.set(2026, 11, 7, 12, 0)
    client.patch("/api/me", json={"kcal_goal": 2500})
    clock.set(2026, 11, 8, 12, 0)
    client.patch("/api/me", json={"kcal_goal": 2800})
    client.patch("/api/me", json={"kcal_goal": 2500})
    conn = db.connect()
    rows = [r["valid_from"] for r in conn.execute("SELECT valid_from FROM goal_history ORDER BY 1")]
    conn.close()
    assert "2026-11-08" not in rows
    assert series(client)["2026-11-08"]["kcal_goal"] == 2500


def test_summary_totals_and_ranges(client):
    add(client, "2026-11-08", 300)
    add(client, "2026-11-08", 200)
    s = series(client)
    assert s["2026-11-08"]["total"] == 500 and s["2026-11-08"]["entries"] == 2
    assert s["2026-11-02"]["total"] == 0
    assert client.get("/api/summary?days=8").status_code == 400


def test_calendar_lists_logged_days_with_goal(client):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-08", 2600)
    data = client.get("/api/calendar").get_json()
    assert data["days"] == [
        {"date": "2026-11-08", "total": 2600, "entries": 1, "kcal_goal": 2500, "goal_direction": "gain"}
    ]


# --- Einschätzung ------------------------------------------------------------

def test_coach_without_goal_or_data(client, fake_ai):
    assert client.get("/api/coach").get_json()["status"] == "no_goal"
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-07", 2000)
    assert client.get("/api/coach").get_json()["status"] == "no_data"
    assert fake_ai.coach_calls == []


def test_coach_ignores_today_and_caches_per_day(client, fake_ai):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-06", 2400)
    add(client, "2026-11-07", 2600)
    first = client.get("/api/coach").get_json()
    assert first["cached"] is False
    data = fake_ai.coach_calls[0][0]
    assert data["tage"][-1]["datum"] == "2026-11-07"
    # Neue Einträge von heute lösen keinen neuen Aufruf aus.
    add(client, "2026-11-08", 1000)
    assert client.get("/api/coach").get_json()["cached"] is True
    assert len(fake_ai.coach_calls) == 1
    # Ein Nachtrag für einen abgeschlossenen Tag schon.
    add(client, "2026-11-05", 1000)
    client.get("/api/coach")
    assert len(fake_ai.coach_calls) == 2


def test_coach_refresh_must_be_post(client, fake_ai):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-06", 2400)
    add(client, "2026-11-07", 2600)
    client.get("/api/coach")
    client.post("/api/coach/refresh")
    assert len(fake_ai.coach_calls) == 2


def test_coach_unlogged_days_are_unknown_not_zero_protein(client, fake_ai):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-06", 2400)
    add(client, "2026-11-07", 2600)
    client.get("/api/coach")
    data = fake_ai.coach_calls[0][0]
    assert data["tage_mit_eintraegen"] == 2
    assert data["durchschnitt_kcal_erfasste_tage"] == 2500
    assert all(d["eiweiss_g"] is None for d in data["tage"])


def test_coach_falls_back_to_last_result_on_ai_error(client, fake_ai, clock):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-06", 2400)
    add(client, "2026-11-07", 2600)
    client.get("/api/coach")
    clock.set(2026, 11, 9, 12, 0)
    fake_ai.fail = "Gemini ist überlastet."
    res = client.get("/api/coach").get_json()
    assert res["stale"] is True and res["headline"] == "Passt"


def test_coach_no_fallback_after_direction_switch(client, fake_ai):
    client.patch("/api/me", json={"kcal_goal": 2500})
    add(client, "2026-11-06", 2400)
    add(client, "2026-11-07", 2600)
    client.get("/api/coach")
    client.patch("/api/me", json={"goal_direction": "lose"})
    fake_ai.fail = "Gemini ist überlastet."
    assert client.get("/api/coach").status_code == 502
