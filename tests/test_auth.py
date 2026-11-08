"""Anmeldung: Registrierungsregeln, Code-Limits, Sitzungen."""

import threading
from datetime import datetime, timedelta, timezone

import auth
import db
from conftest import OWNER


def request_code(anon, email):
    return anon.post("/api/auth/request-code", json={"email": email})


def verify(anon, email, code):
    return anon.post("/api/auth/verify", json={"email": email, "code": code})


def wrong(code):
    return f"{(int(code) + 1) % 1_000_000:06d}"


# --- Wer darf sich registrieren ----------------------------------------------

def test_first_account_may_register_second_not(anon, codes):
    assert request_code(anon, OWNER).status_code == 200
    assert verify(anon, OWNER, codes[OWNER]).status_code == 200
    res = request_code(anon, "fremd@example.com")
    assert res.status_code == 403
    assert "fremd@example.com" not in codes


def test_allowlist_admits_listed_and_rejects_others(anon, codes, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "a@example.com, B@example.com")
    assert request_code(anon, "b@example.com").status_code == 200
    assert verify(anon, "b@example.com", codes["b@example.com"]).status_code == 200
    assert request_code(anon, "c@example.com").status_code == 403


def test_admin_always_allowed_even_if_not_listed(anon, codes, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "a@example.com")
    monkeypatch.setenv("ADMIN_EMAILS", "chef@example.com")
    assert request_code(anon, "chef@example.com").status_code == 200
    assert verify(anon, "chef@example.com", codes["chef@example.com"]).status_code == 200


def test_unknown_and_removed_get_same_message(make_client, anon, monkeypatch):
    make_client("weg@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", "a@example.com")
    removed = request_code(anon, "weg@example.com")
    unknown = request_code(anon, "nie@example.com")
    assert removed.status_code == unknown.status_code == 403
    assert removed.get_json() == unknown.get_json()


def test_invalid_email_rejected(anon):
    assert request_code(anon, "kein-at-zeichen").status_code == 400


# --- Codes -------------------------------------------------------------------

def test_code_is_single_use(anon, codes):
    request_code(anon, OWNER)
    code = codes[OWNER]
    assert verify(anon, OWNER, code).status_code == 200
    assert verify(anon, OWNER, code).status_code == 400


def test_five_wrong_attempts_invalidate_code(anon, codes):
    request_code(anon, OWNER)
    code = codes[OWNER]
    for _ in range(auth.CODE_MAX_ATTEMPTS):
        assert verify(anon, OWNER, wrong(code)).get_json()["error"] == "Der Code stimmt nicht."
    # Auch der richtige Code hilft danach nicht mehr.
    assert verify(anon, OWNER, code).status_code == 400


def test_new_code_invalidates_older_one(anon, codes):
    request_code(anon, OWNER)
    first = codes[OWNER]
    request_code(anon, OWNER)
    second = codes[OWNER]
    # Bei 1 zu einer Million sind beide Codes gleich; dann ist nichts zu prüfen.
    if first != second:
        assert verify(anon, OWNER, first).status_code == 400
    assert verify(anon, OWNER, second).status_code == 200


def test_hourly_limit_per_email(anon):
    for _ in range(auth.CODES_PER_EMAIL_PER_HOUR):
        assert request_code(anon, OWNER).status_code == 200
    assert request_code(anon, OWNER).status_code == 429


def test_daily_limit_per_email(anon):
    # Codes von früher am Tag, außerhalb des Stundenfensters.
    conn = db.connect()
    now = datetime.now(timezone.utc)
    for hours in range(2, 2 + auth.CODES_PER_EMAIL_PER_DAY):
        stamp = (now - timedelta(hours=hours)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO login_codes (email, code_hash, created_at, expires_at, consumed_at) "
            "VALUES (?, 'alt', ?, ?, ?)",
            (OWNER, stamp, stamp, stamp),
        )
    conn.commit()
    conn.close()
    res = request_code(anon, OWNER)
    assert res.status_code == 429
    assert "morgen" in res.get_json()["error"]


def _parallel(n, fn):
    barrier = threading.Barrier(n)
    results = []
    lock = threading.Lock()

    def run():
        conn = db.connect()
        try:
            barrier.wait()
            try:
                out = fn(conn)
            except auth.AuthError as exc:
                out = exc.message
            with lock:
                results.append(out)
        finally:
            conn.close()

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_parallel_wrong_attempts_stay_within_limit(anon, codes):
    request_code(anon, OWNER)
    bad_code = wrong(codes[OWNER])
    results = _parallel(20, lambda conn: auth.verify_login_code(conn, OWNER, bad_code))
    assert results.count("Der Code stimmt nicht.") == auth.CODE_MAX_ATTEMPTS


def test_parallel_correct_code_logs_in_once(anon, codes):
    request_code(anon, OWNER)
    code = codes[OWNER]
    results = _parallel(8, lambda conn: auth.verify_login_code(conn, OWNER, code))
    assert sum(1 for r in results if not isinstance(r, str)) == 1


# --- Sitzungen ---------------------------------------------------------------

def test_api_requires_login(anon):
    assert anon.get("/api/me").status_code == 401
    assert anon.get("/api/entries").status_code == 401
    page = anon.get("/")
    assert page.status_code == 302 and page.headers["Location"].endswith("/login")


def test_logout_ends_session(client):
    assert client.get("/api/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401


def test_logout_all_ends_every_session(make_client):
    phone = make_client(OWNER)
    laptop = make_client(OWNER)
    assert phone.post("/api/auth/logout-all").status_code == 200
    assert phone.get("/api/me").status_code == 401
    assert laptop.get("/api/me").status_code == 401


def test_removed_from_allowlist_loses_session(make_client, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", f"{OWNER},b@example.com")
    owner = make_client(OWNER)
    other = make_client("b@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", OWNER)
    assert other.get("/api/me").status_code == 401
    assert owner.get("/api/me").status_code == 200
    conn = db.connect()
    left = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE u.email = 'b@example.com'"
    ).fetchone()["n"]
    conn.close()
    assert left == 0


def test_expired_session_rejected(client):
    conn = db.connect()
    conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    assert client.get("/api/me").status_code == 401
