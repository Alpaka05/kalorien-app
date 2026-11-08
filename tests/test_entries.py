"""Einträge, Tagesbeginn, Schnellwahl, Gewicht, Export."""

import db
from conftest import OWNER


def add(client, **payload):
    payload.setdefault("desc", "Toast mit Butter")
    return client.post("/api/entries", json=payload)


def day(client, date):
    return client.get(f"/api/entries?date={date}").get_json()["entries"]


# --- Anlegen -----------------------------------------------------------------

def test_free_text_entry_uses_ai(client, fake_ai):
    res = add(client, desc="2 Scheiben Toast")
    assert res.status_code == 201
    entry = res.get_json()
    assert entry["kcal"] == 420.0 and entry["protein"] == 12.0
    assert entry["date"] == "2026-11-08" and entry["time"] == "12:00"
    assert len(fake_ai.meal_calls) == 1


def test_quick_entry_with_values_skips_ai(client, fake_ai):
    res = add(client, desc="Banane", kcal=105, protein="1,3")
    assert res.status_code == 201
    assert res.get_json()["protein"] == 1.3
    assert fake_ai.meal_calls == []


def test_ai_failure_saves_nothing(client, fake_ai):
    fake_ai.fail = "Gemini ist überlastet."
    res = add(client)
    assert res.status_code == 502
    assert res.get_json()["error"] == "Gemini ist überlastet."
    assert day(client, "2026-11-08") == []


def test_estimate_uses_goal_direction(client, fake_ai):
    client.patch("/api/me", json={"goal_direction": "lose"})
    add(client)
    assert fake_ai.meal_calls[0][1] == "lose"


def test_empty_and_too_long_rejected(client):
    assert add(client, desc="  ").status_code == 400
    assert add(client, desc="x" * 501).status_code == 400


def test_backfill_allowed_future_not(client):
    assert add(client, date="2026-11-01", time="08:15", kcal=300).status_code == 201
    assert add(client, date="2026-11-09", kcal=300).status_code == 400
    assert [e["time"] for e in day(client, "2026-11-01")] == ["08:15"]


def test_edit_and_move_entry(client):
    entry = add(client, kcal=300).get_json()
    res = client.patch(f"/api/entries/{entry['id']}", json={"kcal": "350", "date": "2026-11-07"})
    assert res.status_code == 200
    assert day(client, "2026-11-08") == []
    assert day(client, "2026-11-07")[0]["kcal"] == 350


def test_accounts_are_isolated(make_client, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", f"{OWNER},b@example.com")
    a = make_client(OWNER)
    b = make_client("b@example.com")
    entry = add(a, kcal=500).get_json()
    assert day(b, "2026-11-08") == []
    assert b.patch(f"/api/entries/{entry['id']}", json={"kcal": 1}).status_code == 404
    assert b.delete(f"/api/entries/{entry['id']}").status_code == 404
    assert day(a, "2026-11-08")[0]["kcal"] == 500


# --- Tagesbeginn -------------------------------------------------------------

def test_late_snack_counts_for_previous_day(client, clock):
    client.patch("/api/me", json={"day_start_hour": 4})
    clock.set(2026, 11, 9, 1, 30)
    entry = add(client, kcal=200).get_json()
    assert entry["date"] == "2026-11-08"


def test_changing_day_start_rebuckets_and_is_reversible(client):
    add(client, date="2026-11-08", time="01:30", kcal=200)
    add(client, date="2026-11-08", time="09:00", kcal=400)
    res = client.patch("/api/me", json={"day_start_hour": 4}).get_json()
    assert res["moved_entries"] == 1
    assert [e["time"] for e in day(client, "2026-11-07")] == ["01:30"]
    client.patch("/api/me", json={"day_start_hour": 0})
    assert [e["time"] for e in day(client, "2026-11-08")] == ["01:30", "09:00"]


def test_night_entry_sorted_at_end_of_day(client):
    client.patch("/api/me", json={"day_start_hour": 4})
    add(client, date="2026-11-07", time="23:00", kcal=1)
    add(client, date="2026-11-07", time="02:00", kcal=1)
    add(client, date="2026-11-07", time="08:00", kcal=1)
    assert [e["time"] for e in day(client, "2026-11-07")] == ["08:00", "23:00", "02:00"]


# --- Schnellwahl -------------------------------------------------------------

def test_presets_need_two_uses_and_take_latest_values(client):
    add(client, desc="Müsli", date="2026-11-05", time="08:00", kcal=300)
    add(client, desc="müsli ", date="2026-11-06", time="08:00", kcal=350)
    add(client, desc="Pizza", date="2026-11-06", time="19:00", kcal=900)
    presets = client.get("/api/presets").get_json()["presets"]
    assert presets == [{"desc": "müsli", "kcal": 350, "protein": None, "count": 2}]


def test_presets_ignore_entries_older_than_window(client):
    add(client, desc="Alt", date="2026-08-01", kcal=100)
    add(client, desc="Alt", date="2026-08-02", kcal=100)
    assert client.get("/api/presets").get_json()["presets"] == []


# --- Gewicht und Export ------------------------------------------------------

def test_weight_one_value_per_day_and_trend(client):
    client.post("/api/weights", json={"kg": "70,0", "date": "2026-10-01"})
    client.post("/api/weights", json={"kg": 71.0, "date": "2026-11-08"})
    client.post("/api/weights", json={"kg": 71.5, "date": "2026-11-08"})
    data = client.get("/api/weights").get_json()
    assert len(data["entries"]) == 2
    assert data["latest"]["kg"] == 71.5
    assert data["trend"] == {"delta": 1.5, "from_date": "2026-10-01"}


def test_csv_export_contains_own_entries(client):
    add(client, desc="Apfel; grün", kcal=80)
    res = client.get("/api/export.csv")
    text = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "Datum;Uhrzeit;Beschreibung;kcal;Eiweiss_g" in text
    assert '"Apfel; grün"' in text


def test_settings_validation(client):
    assert client.patch("/api/me", json={"kcal_goal": 100}).status_code == 400
    assert client.patch("/api/me", json={"goal_direction": "halten"}).status_code == 400
    assert client.patch("/api/me", json={"day_start_hour": 12}).status_code == 400
    assert client.patch("/api/me", json={"ai_model": "claude"}).status_code == 403
    me = client.patch("/api/me", json={"kcal_goal": "2800", "protein_goal": ""}).get_json()
    assert me["kcal_goal"] == 2800 and me["protein_goal"] is None


def test_index_page_has_versioned_assets(client):
    html = client.get("/").get_data(as_text=True)
    assert "__ASSET_V__" not in html
    assert "/app.js?v=" in html


def test_orphan_db_rows_untouched_by_other_user(client):
    # Sicherheitsnetz für die SQL-Filter: jede Zeile trägt die user_id.
    add(client, kcal=10)
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) AS n FROM entries WHERE user_id IS NULL").fetchone()["n"] == 0
    conn.close()
