"""Gemeinsame Fixtures: frische Datenbank je Test, feste Uhr, Login ohne Mail,
KI ohne Netz.

Die Umgebung muss stehen, bevor app.py importiert wird: db.py liest DB_PATH
beim Import, auth.py den SECRET_KEY, und app.py legt beim Import schon die
Datenbank an.
"""

import os
import sys
import tempfile
from datetime import datetime

import pytest

_BOOT_DIR = tempfile.mkdtemp(prefix="kalorien-test-")
os.environ["DB_PATH"] = os.path.join(_BOOT_DIR, "boot.db")
os.environ["SECRET_KEY"] = "test-secret-key-nur-fuer-die-tests"
os.environ["APP_TZ"] = "Europe/Berlin"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
for name in ("ALLOWED_EMAILS", "ADMIN_EMAILS", "REGISTRATION_OPEN", "SMTP_HOST", "COOKIE_SECURE"):
    os.environ.pop(name, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai  # noqa: E402
import app as app_module  # noqa: E402
import db  # noqa: E402
import mailer  # noqa: E402
import timeutil  # noqa: E402

OWNER = "ich@example.com"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine eigene, frisch migrierte Datenbank."""
    for name in ("ALLOWED_EMAILS", "ADMIN_EMAILS", "REGISTRATION_OPEN"):
        monkeypatch.delenv(name, raising=False)
    path = str(tmp_path / "kalorien.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return path


class Clock:
    """Feste Uhr in der App-Zeitzone; `set` stellt sie um."""

    def __init__(self):
        self.now = datetime(2026, 11, 8, 12, 0, tzinfo=timeutil.TZ)

    def set(self, *args):
        self.now = datetime(*args, tzinfo=timeutil.TZ)

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(timeutil, "now_local", c)
    return c


@pytest.fixture(autouse=True)
def codes(monkeypatch):
    """Fängt Login-Codes ab, statt sie zu verschicken: {email: letzter Code}."""
    sent = {}

    def fake_send(email, code, minutes_valid):
        sent[email] = code
        return "log"

    monkeypatch.setattr(mailer, "send_login_code", fake_send)
    return sent


class FakeAI:
    """Ersetzt beide KI-Aufrufe; zählt mit und kann einen Fehler werfen."""

    def __init__(self):
        self.meal_calls = []
        self.coach_calls = []
        self.fail = None
        self.meal = {"kcal": 420.0, "protein": 12.0}

    def estimate_meal(self, description, direction="gain", model="gemini", image=None):
        self.meal_calls.append((description, direction, model))
        if self.fail:
            raise ai.AIError(self.fail)
        return {"normalized": description.strip(), "components": [], **self.meal}

    def coach_analysis(self, data, direction="gain", model="gemini"):
        self.coach_calls.append((data, direction, model))
        if self.fail:
            raise ai.AIError(self.fail)
        return {
            "status": "on_track",
            "headline": "Passt",
            "message": f"{data['tage_mit_eintraegen']} Tage erfasst.",
            "tips": [],
        }


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ai, "estimate_meal", fake.estimate_meal)
    monkeypatch.setattr(ai, "coach_analysis", fake.coach_analysis)
    return fake


@pytest.fixture
def make_client(codes):
    """Erzeugt angemeldete Test-Clients: make_client("a@example.com")."""

    def make(email=OWNER):
        client = app_module.app.test_client()
        res = client.post("/api/auth/request-code", json={"email": email})
        assert res.status_code == 200, res.get_json()
        res = client.post("/api/auth/verify", json={"email": email, "code": codes[email]})
        assert res.status_code == 200, res.get_json()
        return client

    return make


@pytest.fixture
def client(make_client):
    return make_client(OWNER)


@pytest.fixture
def anon():
    return app_module.app.test_client()
