"""Zeit-Helfer und Migrationen der Datenbank."""

import sqlite3

import pytest

import db
import timeutil


# --- Zeit --------------------------------------------------------------------

@pytest.mark.parametrize(
    "date, time, start, expected",
    [
        ("2026-11-08", "01:30", 0, "2026-11-08"),
        ("2026-11-08", "01:30", 4, "2026-11-07"),
        ("2026-11-08", "04:00", 4, "2026-11-08"),
        ("2026-03-01", "03:59", 4, "2026-02-28"),
    ],
)
def test_logical_date_of(date, time, start, expected):
    assert timeutil.logical_date_of(date, time, start) == expected


@pytest.mark.parametrize("start", range(12))
def test_calendar_and_logical_date_are_inverse(start):
    for time in ("00:00", "03:30", "11:59", "12:00", "23:59"):
        logical = timeutil.logical_date_of("2026-01-01", time, start)
        assert timeutil.calendar_date_of(logical, time, start) == "2026-01-01"


def test_logical_today_follows_day_start(clock):
    clock.set(2026, 11, 9, 2, 0)
    assert timeutil.logical_today(0) == "2026-11-09"
    assert timeutil.logical_today(4) == "2026-11-08"


def test_date_range_ends_on_end():
    assert timeutil.date_range_iso(3, "2026-03-01") == ["2026-02-27", "2026-02-28", "2026-03-01"]


# --- Migrationen -------------------------------------------------------------

LEGACY_SCHEMA = """
CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    "desc" TEXT NOT NULL,
    kcal REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    kcal_goal REAL,
    protein_goal REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE goal_history (
    user_id INTEGER NOT NULL,
    valid_from TEXT NOT NULL,
    kcal_goal REAL,
    protein_goal REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, valid_from)
);
"""


def _cols(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_init_db_is_idempotent(fresh_db):
    db.init_db()
    db.init_db()
    assert {"day_start_hour", "goal_direction", "show_presets", "ai_model"} <= _cols(fresh_db, "users")


def test_migrates_single_user_database(tmp_path, monkeypatch):
    path = str(tmp_path / "alt.db")
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    # Damals in UTC gespeichert: 23:30 UTC im Sommer ist 01:30 am Folgetag in Berlin.
    conn.execute(
        "INSERT INTO entries (entry_date, entry_time, \"desc\", kcal, created_at) "
        "VALUES ('2026-07-01', '23:30', 'Nachtsnack', 300, 'x')"
    )
    conn.execute(
        "INSERT INTO users (email, kcal_goal, created_at) VALUES ('ich@example.com', 2500, 'x')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    db.init_db()  # zweiter Start darf nichts doppelt machen

    assert {"user_id", "protein"} <= _cols(path, "entries")
    assert "goal_direction" in _cols(path, "goal_history")
    conn = db.connect()
    entry = conn.execute("SELECT entry_date, entry_time, user_id FROM entries").fetchone()
    assert (entry["entry_date"], entry["entry_time"]) == ("2026-07-02", "01:30")
    history = conn.execute("SELECT valid_from, kcal_goal, goal_direction FROM goal_history").fetchall()
    assert [tuple(r) for r in history] == [("0000-01-01", 2500, "gain")]
    user = conn.execute("SELECT * FROM users").fetchone()
    assert user["goal_direction"] == "gain" and user["day_start_hour"] == 0

    # Der erste Login übernimmt die Einträge ohne Besitzer.
    assert db.adopt_orphan_entries(conn, user["id"]) == 1
    conn.close()


def test_goals_by_date_before_history_has_no_goal(fresh_db):
    conn = db.connect()
    conn.execute(
        "INSERT INTO goal_history (user_id, valid_from, kcal_goal, goal_direction, created_at) "
        "VALUES (1, '2026-11-05', 2000, 'lose', 'x')"
    )
    goals = db.goals_by_date(conn, 1, ["2026-11-04", "2026-11-05", "2026-11-06"])
    conn.close()
    assert goals["2026-11-04"] == {"kcal_goal": None, "protein_goal": None, "goal_direction": "gain"}
    assert goals["2026-11-06"]["kcal_goal"] == 2000
    assert goals["2026-11-06"]["goal_direction"] == "lose"
