"""Kalorien-Tagebuch – Flask-Backend.

Alle Daten sind pro Konto getrennt; jede API-Route filtert konsequent nach
`user_id` aus der Session.
"""

import base64
import binascii
import csv
import functools
import io
import ipaddress
import json
import logging
import mimetypes
import os
import re
from hashlib import sha256

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    redirect,
    request,
)

import ai
import auth
import db
import habits
import mailer
from timeutil import (
    calendar_date_of,
    date_range_iso,
    day_offset_iso,
    local_time_hhmm,
    logical_date_of,
    logical_today,
    today_iso,
    utc_now_iso,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("kalorien")

COOKIE_NAME = "kcal_session"
# Leer = automatisch: Secure wird gesetzt, wenn die Anfrage über HTTPS kam.
# Ohne diese Automatik würde die Anmeldung beim Aufruf über http://<ip>:5000
# stillschweigend scheitern, weil der Browser das Secure-Cookie verwirft.
_COOKIE_SECURE_ENV = os.environ.get("COOKIE_SECURE", "").strip().lower()
# Die App läuft hinter einem Reverse Proxy bzw. Cloudflare-Tunnel; ohne diese
# Header hätten alle Nutzer dieselbe Quell-IP und würden sich beim
# Ratelimit gegenseitig aussperren.
TRUST_PROXY_IP = os.environ.get("TRUST_PROXY_IP", "true").strip().lower() not in (
    "0",
    "false",
    "no",
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ALLOWED_RANGES = (7, 14, 30, 90)

# Python kennt diese Endung erst ab 3.13; im Container (3.12) käme das
# Manifest sonst als octet-stream und würde wegen nosniff verworfen.
mimetypes.add_type("application/manifest+json", ".webmanifest")

app = Flask(__name__, static_folder="static", static_url_path="")
# Ein Foto kommt als base64 im JSON. Der Browser verkleinert es vorher auf
# ~1600px (ein paar hundert KB); die Grenze fängt nur Ausreißer ab und liegt
# über MAX_IMAGE_BYTES, weil base64 ein Drittel größer ist als die Datei.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
db.init_db()

# Claude nimmt höchstens 5 MB je Bild an.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
_DATA_URL = re.compile(r"^data:(?P<type>image/[\w.+-]+);base64,(?P<data>.+)$", re.DOTALL)


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------

def _peer_is_local() -> bool:
    """Kam die Anfrage vom Reverse Proxy im eigenen Netz?"""
    try:
        peer = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return peer.is_loopback or peer.is_private or peer.is_link_local


def client_ip() -> str:
    # Die Header werden nur ausgewertet, wenn die Verbindung tatsächlich vom
    # lokalen Proxy kommt. Andernfalls könnte sie jeder selbst setzen und damit
    # das Ratelimit mit beliebigen Fantasie-IPs umgehen.
    if TRUST_PROXY_IP and _peer_is_local():
        cf = request.headers.get("CF-Connecting-IP", "").strip()
        if cf:
            return cf[:64]
        forwarded = request.headers.get("X-Forwarded-For", "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "unbekannt")[:64]


def cookie_secure() -> bool:
    if _COOKIE_SECURE_ENV in ("1", "true", "yes", "on"):
        return True
    if _COOKIE_SECURE_ENV in ("0", "false", "no", "off"):
        return False
    proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    if proto:
        return proto == "https"
    return request.is_secure


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def bad(message: str, status: int = 400):
    return jsonify({"error": message}), status


def parse_image(value) -> dict:
    """Prüft ein Foto als data:-URL und gibt es so zurück, wie ai.py es braucht.

    Das Foto wird nur an die KI weitergereicht und nirgends gespeichert.
    """
    match = _DATA_URL.match(value) if isinstance(value, str) else None
    if not match or match["type"] not in IMAGE_TYPES:
        raise ValueError("Das Foto konnte nicht gelesen werden (JPEG, PNG oder WebP).")
    data = match["data"]
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Das Foto konnte nicht gelesen werden.") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Das Foto ist zu groß.")
    return {"media_type": match["type"], "data": data}


def parse_date(value, field: str = "Datum") -> str:
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ValueError(f"{field} muss im Format JJJJ-MM-TT angegeben werden.")
    from datetime import date

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} ist kein gültiges Datum.") from None
    # Extreme Jahre sind formal gültig, aber späteres Rechnen damit (etwa
    # "30 Tage davor") läuft aus dem Wertebereich und würde die Auswertung
    # dauerhaft mit einem Serverfehler blockieren.
    if not date(2000, 1, 1) <= parsed <= date(2100, 12, 31):
        raise ValueError(f"{field} muss zwischen 2000 und 2100 liegen.")
    return value


def parse_time(value) -> str:
    if not isinstance(value, str) or not TIME_RE.match(value.strip()):
        raise ValueError("Uhrzeit muss im Format HH:MM angegeben werden.")
    return value.strip()


def parse_number(value, field: str, lo: float, hi: float) -> float:
    # Deutsche Eingaben kommen mit Komma als Dezimaltrennzeichen; das Frontend
    # rechnet es um, hier steht es als Sicherheitsnetz.
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} muss eine Zahl sein.") from None
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field} muss eine Zahl sein.")
    if not lo <= number <= hi:
        raise ValueError(f"{field} muss zwischen {lo:g} und {hi:g} liegen.")
    return number


def require_user(view):
    """Öffnet eine DB-Verbindung, prüft die Session und schließt danach wieder."""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        conn = db.connect()
        try:
            user = auth.user_for_token(conn, request.cookies.get(COOKIE_NAME, ""))
            if not user:
                return bad("Bitte melde dich an.", 401)
            g.conn = conn
            g.user = user
            return view(*args, **kwargs)
        finally:
            conn.close()

    return wrapper


def ai_model(user) -> str:
    """Das KI-Modell, das für dieses Konto tatsächlich benutzt wird.

    Die gespeicherte Wahl zählt nur für Admins und nur, wenn das Modell
    gerade nutzbar ist (Claude braucht ANTHROPIC_API_KEY). In jedem anderen
    Fall Gemini – auch wenn jemand einen Admin von der Liste streicht, fällt
    sein Konto damit sofort auf Gemini zurück.
    """
    try:
        chosen = user["ai_model"] or ai.DEFAULT_MODEL
    except (KeyError, IndexError):
        chosen = ai.DEFAULT_MODEL
    if chosen != ai.DEFAULT_MODEL and auth.is_admin(user["email"]) and ai.model_available(chosen):
        return chosen
    return ai.DEFAULT_MODEL


def ai_model_options() -> list[dict]:
    return [
        {"id": key, "label": label, "available": ai.model_available(key)}
        for key, label in ai.AI_MODELS.items()
    ]


def day_start(user) -> int:
    """Persönlicher Tagesbeginn in Stunden (0 = Mitternacht)."""
    try:
        return int(user["day_start_hour"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        return 0


# Richtung des Tagesziels. "gain": kcal_goal ist eine Untergrenze, die erreicht
# werden soll. "lose": kcal_goal ist eine Obergrenze, unter der man bleiben
# will. Alles andere in der App bleibt gleich – nur die Bewertung dreht sich.
GOAL_DIRECTIONS = ("gain", "lose")


def goal_direction(user) -> str:
    """Zielrichtung der Person; "gain", wenn nichts Gültiges gespeichert ist."""
    try:
        value = user["goal_direction"]
    except (KeyError, IndexError, TypeError):
        return "gain"
    return value if value in GOAL_DIRECTIONS else "gain"


def show_presets(user) -> bool:
    """Ob die Schnellwahl-Chips angezeigt werden; an, wenn nichts gespeichert ist."""
    try:
        value = user["show_presets"]
    except (KeyError, IndexError, TypeError):
        return True
    return value is None or bool(value)


def user_today(user) -> str:
    """Tag, dem "jetzt" für diese Person zugerechnet wird."""
    return logical_today(day_start(user))


def parse_entry_date(value) -> str:
    """Datum eines Eintrags: nachtragen ja, vorausbuchen nein."""
    entry_date = parse_date(value)
    if entry_date > user_today(g.user):
        raise ValueError("Einträge für künftige Tage gehen nicht.")
    return entry_date


def entry_json(row) -> dict:
    return {
        "id": row["id"],
        "date": row["entry_date"],
        "time": row["entry_time"],
        "desc": row["desc"],
        "kcal": row["kcal"],
        "protein": row["protein"],
    }


# --------------------------------------------------------------------------
# HTML ausliefern (mit Versionsstempel an CSS und JS)
# --------------------------------------------------------------------------

# Verweise der Form /datei.css?v=__ASSET_V__ bekommen je Datei ihre eigene
# Kennung. Ein gemeinsamer Zeitstempel über alle Dateien wäre zu grob: ändert
# sich das CSS, während das JS schon neuer ist, bliebe das Maximum gleich und
# die alte CSS würde weiter aus dem Zwischenspeicher kommen.
_ASSET_REF = re.compile(r"(?P<path>/(?P<name>[\w.-]+\.(?:css|js)))\?v=__ASSET_V__")
_asset_tokens: dict[str, tuple[tuple[float, int], str]] = {}


def asset_token(name: str) -> str:
    """Kurzer Hash über den Inhalt einer statischen Datei.

    Der Hash statt der Änderungszeit, weil Zeitstempel unzuverlässig sind:
    ein Wiederherstellen aus einem Archiv, eine zurückgestellte Uhr oder zwei
    Änderungen in derselben Sekunde würden sonst dieselbe Kennung ergeben und
    die alte Datei bliebe im Zwischenspeicher hängen.
    """
    path = os.path.join(app.static_folder, name)
    try:
        info = os.stat(path)
    except OSError:
        return "0"
    signature = (info.st_mtime, info.st_size)
    cached = _asset_tokens.get(name)
    if cached and cached[0] == signature:
        return cached[1]
    try:
        with open(path, "rb") as fh:
            token = sha256(fh.read()).hexdigest()[:10]
    except OSError:
        return "0"
    _asset_tokens[name] = (signature, token)
    return token


def render_page(name: str) -> Response:
    path = os.path.join(app.static_folder, name)
    try:
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
    except OSError:
        log.error("Seitenvorlage %s fehlt oder ist nicht lesbar", name)
        return Response(
            "Die Seite ist nicht verfügbar. Bitte im Container-Log nachsehen.",
            status=500,
            mimetype="text/plain",
        )
    html = _ASSET_REF.sub(
        lambda m: f"{m.group('path')}?v={asset_token(m.group('name'))}", html
    )
    response = Response(html, mimetype="text/html")
    # Die Seite selbst trägt die Kennungen, darf also nie aus dem
    # Zwischenspeicher kommen – sonst verweist sie auf veraltete Dateien.
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.errorhandler(Exception)
def handle_unexpected(exc: Exception):
    """Auf /api/* immer JSON zurückgeben – das Frontend parst nur JSON."""
    status = getattr(exc, "code", 500)
    if not isinstance(status, int):
        status = 500
    if status >= 500:
        log.exception("Unbehandelter Fehler bei %s %s", request.method, request.path)
    if request.path.startswith("/api/"):
        message = (
            "Auf dem Server ist ein Fehler aufgetreten."
            if status >= 500
            else getattr(exc, "description", "Anfrage nicht möglich.")
        )
        return jsonify({"error": message}), status
    return exc if hasattr(exc, "code") else ("Interner Fehler", 500)


@app.errorhandler(413)
def too_large(exc):
    return bad("Das Foto ist zu groß.", 413)


@app.after_request
def security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


# --------------------------------------------------------------------------
# Seiten
# --------------------------------------------------------------------------

@app.route("/")
def index():
    conn = db.connect()
    try:
        user = auth.user_for_token(conn, request.cookies.get(COOKIE_NAME, ""))
    finally:
        conn.close()
    if not user:
        return redirect("/login", code=302)
    return render_page("index.html")


@app.route("/login")
def login_page():
    return render_page("login.html")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Anmeldung
# --------------------------------------------------------------------------

@app.route("/api/auth/request-code", methods=["POST"])
def request_code():
    conn = db.connect()
    try:
        email = auth.normalize_email(body().get("email"))
        code = auth.create_login_code(conn, email, client_ip())
    except auth.AuthError as exc:
        return bad(exc.message, exc.status)
    finally:
        conn.close()

    try:
        delivery = mailer.send_login_code(email, code, auth.CODE_TTL_MINUTES)
    except Exception:
        return bad(
            "Der Code konnte nicht per E-Mail verschickt werden. "
            "Bitte prüfe die SMTP-Einstellungen.",
            502,
        )
    return jsonify({"ok": True, "delivery": delivery, "email": email})


@app.route("/api/auth/verify", methods=["POST"])
def verify_code():
    payload = body()
    conn = db.connect()
    try:
        email = auth.normalize_email(payload.get("email"))
        user = auth.verify_login_code(conn, email, payload.get("code"))
        token = auth.create_session(conn, user["id"])
    except auth.AuthError as exc:
        return bad(exc.message, exc.status)
    finally:
        conn.close()

    response = jsonify({"ok": True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=auth.SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=cookie_secure(),
        samesite="Lax",
        path="/",
    )
    return response


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    conn = db.connect()
    try:
        auth.destroy_session(conn, request.cookies.get(COOKIE_NAME, ""))
    finally:
        conn.close()
    response = jsonify({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.route("/api/auth/logout-all", methods=["POST"])
@require_user
def logout_all():
    # Etwa nach einem verlorenen Handy: beendet auch die Sitzung, mit der die
    # Anfrage kommt.
    auth.destroy_all_sessions(g.conn, g.user["id"])
    response = jsonify({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# --------------------------------------------------------------------------
# Konto und Einstellungen
# --------------------------------------------------------------------------

@app.route("/api/me", methods=["GET"])
@require_user
def me():
    user = g.user
    return jsonify(
        {
            "email": user["email"],
            "display_name": user["display_name"],
            "kcal_goal": user["kcal_goal"],
            "protein_goal": user["protein_goal"],
            "day_start_hour": day_start(user),
            "goal_direction": goal_direction(user),
            "show_presets": show_presets(user),
            "mail_configured": mailer.is_configured(),
            **ai_settings(user),
        }
    )


def ai_settings(user) -> dict:
    """Modellwahl nur für Admins – alle anderen bekommen die Felder gar nicht."""
    if not auth.is_admin(user["email"]):
        return {"is_admin": False}
    return {
        "is_admin": True,
        "ai_model": user["ai_model"] or ai.DEFAULT_MODEL,
        "ai_model_active": ai_model(user),
        "ai_models": ai_model_options(),
    }


@app.route("/api/me", methods=["PATCH"])
@require_user
def update_me():
    payload = body()
    fields, values = [], []
    try:
        if "kcal_goal" in payload:
            value = payload["kcal_goal"]
            fields.append("kcal_goal = ?")
            values.append(
                None if value in (None, "") else parse_number(value, "Kalorienziel", 500, 12000)
            )
        if "protein_goal" in payload:
            value = payload["protein_goal"]
            fields.append("protein_goal = ?")
            values.append(
                None if value in (None, "") else parse_number(value, "Eiweißziel", 10, 500)
            )
        if "display_name" in payload:
            name = (payload["display_name"] or "").strip()[:60]
            fields.append("display_name = ?")
            values.append(name or None)
        if "goal_direction" in payload:
            direction = str(payload["goal_direction"] or "").strip()
            if direction not in GOAL_DIRECTIONS:
                return bad("Ziel muss „Zunehmen“ oder „Abnehmen“ sein.")
            fields.append("goal_direction = ?")
            values.append(direction)
        if "show_presets" in payload:
            if not isinstance(payload["show_presets"], bool):
                return bad("show_presets muss true oder false sein.")
            fields.append("show_presets = ?")
            values.append(1 if payload["show_presets"] else 0)
        if "ai_model" in payload:
            # Die Prüfung liegt hier auf dem Server, nicht nur im ausgeblendeten
            # Feld: ein nachgebauter Request eines Nicht-Admins scheitert.
            if not auth.is_admin(g.user["email"]):
                return bad("Nur Admin-Konten können das KI-Modell wählen.", 403)
            model = str(payload["ai_model"] or "").strip()
            if model not in ai.AI_MODELS:
                return bad("Unbekanntes KI-Modell.")
            if not ai.model_available(model):
                return bad("Für Claude fehlt ANTHROPIC_API_KEY in der .env.")
            fields.append("ai_model = ?")
            values.append(model)
        new_start = None
        if "day_start_hour" in payload:
            new_start = int(parse_number(payload["day_start_hour"], "Tagesbeginn", 0, 11))
            fields.append("day_start_hour = ?")
            values.append(new_start)
    except ValueError as exc:
        return bad(str(exc))

    if fields:
        old_start = day_start(g.user)
        values.append(g.user["id"])
        g.conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        moved = 0
        if new_start is not None and new_start != old_start:
            moved = rebucket_entries(g.conn, g.user["id"], old_start, new_start)
            rebucket_checkins(g.conn, g.user["id"], old_start, new_start)
        if any(k in payload for k in ("kcal_goal", "protein_goal", "goal_direction")):
            record_goal_change(g.conn, g.user["id"])
        g.conn.commit()

    row = g.conn.execute(
        "SELECT email, display_name, kcal_goal, protein_goal, day_start_hour, "
        "       goal_direction, show_presets, ai_model "
        "FROM users WHERE id = ?",
        (g.user["id"],),
    ).fetchone()
    result = dict(row)
    del result["ai_model"]
    result.update(ai_settings(row))
    result["day_start_hour"] = int(result["day_start_hour"] or 0)
    result["goal_direction"] = goal_direction(row)
    result["show_presets"] = show_presets(row)
    result["moved_entries"] = moved if fields else 0
    return jsonify(result)


def record_goal_change(conn, user_id: int) -> None:
    """Hält Ziel und Zielrichtung im Verlauf fest, gültig ab dem heutigen Tag.

    Mehrere Änderungen am selben Tag überschreiben sich; es zählt die letzte.
    Frühere Tage behalten Ziel und Richtung, die an ihnen galten.
    """
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    today = user_today(user)
    direction = goal_direction(user)
    previous = conn.execute(
        "SELECT kcal_goal, protein_goal, goal_direction FROM goal_history "
        "WHERE user_id = ? AND valid_from < ? ORDER BY valid_from DESC LIMIT 1",
        (user_id, today),
    ).fetchone()
    if previous and (
        previous["kcal_goal"], previous["protein_goal"], previous["goal_direction"]
    ) == (user["kcal_goal"], user["protein_goal"], direction):
        # Zurück auf das Ziel von gestern: ein eigener Eintrag für heute wäre
        # nur Rauschen.
        conn.execute(
            "DELETE FROM goal_history WHERE user_id = ? AND valid_from = ?",
            (user_id, today),
        )
        return
    conn.execute(
        "INSERT INTO goal_history "
        "(user_id, valid_from, kcal_goal, protein_goal, goal_direction, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, valid_from) DO UPDATE SET "
        "kcal_goal = excluded.kcal_goal, protein_goal = excluded.protein_goal, "
        "goal_direction = excluded.goal_direction, created_at = excluded.created_at",
        (user_id, today, user["kcal_goal"], user["protein_goal"], direction, utc_now_iso()),
    )


def rebucket_entries(conn, user_id: int, old_start: int, new_start: int) -> int:
    """Bucht bestehende Einträge auf den neuen Tagesbeginn um.

    Ohne das würde die Einstellung nur für neue Einträge gelten und der
    Verlauf wäre eine Mischung aus zwei Zählweisen. Der echte Kalendertag
    lässt sich aus dem gespeicherten Datum und der Uhrzeit eindeutig
    zurückrechnen, solange der alte Tagesbeginn bekannt ist – die Umbuchung
    ist damit exakt und durch Zurückstellen wieder umkehrbar.
    """
    rows = conn.execute(
        "SELECT id, entry_date, entry_time FROM entries WHERE user_id = ?", (user_id,)
    ).fetchall()
    changes = []
    for row in rows:
        try:
            calendar = calendar_date_of(row["entry_date"], row["entry_time"], old_start)
            target = logical_date_of(calendar, row["entry_time"], new_start)
        except (ValueError, TypeError):
            continue
        if target != row["entry_date"]:
            changes.append((target, row["id"]))
    if changes:
        conn.executemany(
            "UPDATE entries SET entry_date = ? WHERE id = ?", changes
        )
    return len(changes)


def rebucket_checkins(conn, user_id: int, old_start: int, new_start: int) -> int:
    """Wie rebucket_entries, für die Einträge der Ziele.

    Nachgetragene Tage ohne Uhrzeit bleiben, wo sie sind – ohne Uhrzeit lässt
    sich nicht sagen, ob sie vor oder nach dem Tagesbeginn lagen.
    """
    rows = conn.execute(
        "SELECT id, checkin_date, checkin_time FROM habit_checkins "
        "WHERE user_id = ? AND checkin_time IS NOT NULL",
        (user_id,),
    ).fetchall()
    changes = []
    for row in rows:
        try:
            calendar = calendar_date_of(row["checkin_date"], row["checkin_time"], old_start)
            target = logical_date_of(calendar, row["checkin_time"], new_start)
        except (ValueError, TypeError):
            continue
        if target != row["checkin_date"]:
            changes.append((target, row["id"]))
    if changes:
        conn.executemany("UPDATE habit_checkins SET checkin_date = ? WHERE id = ?", changes)
    return len(changes)


# --------------------------------------------------------------------------
# Einträge
# --------------------------------------------------------------------------

@app.route("/api/entries", methods=["GET"])
@require_user
def list_entries():
    start = day_start(g.user)
    try:
        entry_date = parse_date(request.args.get("date") or user_today(g.user))
    except ValueError as exc:
        return bad(str(exc))
    # Bei einem Tagesbeginn von z. B. 04:00 gehört 01:30 chronologisch ans Ende
    # des Tages, nicht an den Anfang – sonst steht der Nachtsnack ganz oben.
    rows = g.conn.execute(
        'SELECT id, entry_date, entry_time, "desc", kcal, protein FROM entries '
        "WHERE user_id = ? AND entry_date = ? "
        "ORDER BY CASE WHEN entry_time < ? THEN 1 ELSE 0 END, entry_time ASC, id ASC",
        (g.user["id"], entry_date, f"{start:02d}:00"),
    ).fetchall()
    return jsonify(
        {
            "date": entry_date,
            "calendar_date": today_iso(),
            "day_start_hour": start,
            "entries": [entry_json(r) for r in rows],
        }
    )


@app.route("/api/entries", methods=["POST"])
@require_user
def add_entry():
    payload = body()
    description = (payload.get("desc") or "").strip()
    has_image = bool(payload.get("image"))
    if not description and not has_image:
        return bad("Bitte gib ein, was du gegessen oder getrunken hast.")
    if len(description) > 500:
        return bad("Die Beschreibung ist zu lang (maximal 500 Zeichen).")

    try:
        entry_date = (
            parse_entry_date(payload["date"]) if payload.get("date") else user_today(g.user)
        )
        entry_time = parse_time(payload["time"]) if payload.get("time") else local_time_hhmm()
        # Schnell-Eintrag aus der Schnellwahl: Werte sind bekannt, die KI wird
        # nicht gebraucht (spart Zeit und API-Kosten).
        if payload.get("kcal") is not None and not has_image:
            kcal = parse_number(payload["kcal"], "Kalorien", 0, 20000)
            protein = (
                parse_number(payload["protein"], "Eiweiß", 0, 1000)
                if payload.get("protein") is not None
                else None
            )
            normalized = description
        else:
            image = parse_image(payload["image"]) if has_image else None
            estimate = ai.estimate_meal(
                description, goal_direction(g.user), ai_model(g.user), image
            )
            kcal, protein, normalized = (
                estimate["kcal"],
                estimate["protein"],
                estimate["normalized"],
            )
    except ValueError as exc:
        return bad(str(exc))
    except ai.AIError as exc:
        return bad(str(exc), 502)

    cur = g.conn.execute(
        'INSERT INTO entries (user_id, entry_date, entry_time, "desc", kcal, protein, created_at) '
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["id"], entry_date, entry_time, normalized, kcal, protein, utc_now_iso()),
    )
    g.conn.commit()
    row = g.conn.execute(
        'SELECT id, entry_date, entry_time, "desc", kcal, protein FROM entries WHERE id = ?',
        (cur.lastrowid,),
    ).fetchone()
    return jsonify(entry_json(row)), 201


# Schnellwahl aus den eigenen Einträgen: was in diesem Zeitraum mindestens so
# oft vorkam, wird ein Knopf.
PRESET_DAYS = 60
PRESET_MIN_COUNT = 2
PRESET_LIMIT = 20


def preset_key(description: str) -> str:
    """Vergleichsschlüssel: gleiche Beschreibung trotz anderer Schreibweise."""
    return " ".join(description.split()).casefold()


@app.route("/api/presets", methods=["GET"])
@require_user
def list_presets():
    today = user_today(g.user)
    rows = g.conn.execute(
        'SELECT entry_date, entry_time, id, "desc", kcal, protein FROM entries '
        "WHERE user_id = ? AND entry_date BETWEEN ? AND ? "
        "ORDER BY entry_date DESC, entry_time DESC, id DESC",
        (g.user["id"], day_offset_iso(PRESET_DAYS - 1, today), today),
    ).fetchall()
    # Neueste zuerst: der erste Treffer je Gericht liefert die Werte, damit
    # eine nachträgliche Korrektur für alle künftigen Tipps gilt.
    groups: dict[str, dict] = {}
    for rank, row in enumerate(rows):
        key = preset_key(row["desc"])
        if not key:
            continue
        group = groups.get(key)
        if group is None:
            groups[key] = {
                "desc": " ".join(row["desc"].split()),
                "kcal": round(row["kcal"]),
                "protein": None if row["protein"] is None else round(row["protein"]),
                "count": 1,
                "recency": rank,
            }
        else:
            group["count"] += 1
    presets = sorted(
        (p for p in groups.values() if p["count"] >= PRESET_MIN_COUNT),
        key=lambda p: (-p["count"], p["recency"]),
    )[:PRESET_LIMIT]
    for preset in presets:
        del preset["recency"]
    return jsonify(
        {
            "days": PRESET_DAYS,
            "min_count": PRESET_MIN_COUNT,
            "presets": presets,
        }
    )


@app.route("/api/entries/<int:entry_id>", methods=["PATCH"])
@require_user
def update_entry(entry_id: int):
    payload = body()
    fields, values = [], []
    try:
        if "desc" in payload:
            description = (payload["desc"] or "").strip()
            if not description:
                return bad("Die Beschreibung darf nicht leer sein.")
            fields.append('"desc" = ?')
            values.append(description[:500])
        if "kcal" in payload:
            fields.append("kcal = ?")
            values.append(parse_number(payload["kcal"], "Kalorien", 0, 20000))
        if "protein" in payload:
            value = payload["protein"]
            fields.append("protein = ?")
            values.append(
                None if value in (None, "") else parse_number(value, "Eiweiß", 0, 1000)
            )
        if "time" in payload:
            fields.append("entry_time = ?")
            values.append(parse_time(payload["time"]))
        if "date" in payload:
            fields.append("entry_date = ?")
            values.append(parse_entry_date(payload["date"]))
    except ValueError as exc:
        return bad(str(exc))
    if not fields:
        return bad("Es wurde nichts geändert.")

    values.extend([entry_id, g.user["id"]])
    cur = g.conn.execute(
        f"UPDATE entries SET {', '.join(fields)} WHERE id = ? AND user_id = ?", values
    )
    if not cur.rowcount:
        return bad("Eintrag nicht gefunden.", 404)
    g.conn.commit()
    row = g.conn.execute(
        'SELECT id, entry_date, entry_time, "desc", kcal, protein FROM entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    return jsonify(entry_json(row))


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
@require_user
def delete_entry(entry_id: int):
    cur = g.conn.execute(
        "DELETE FROM entries WHERE id = ? AND user_id = ?", (entry_id, g.user["id"])
    )
    if not cur.rowcount:
        return bad("Eintrag nicht gefunden.", 404)
    g.conn.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Verlauf
# --------------------------------------------------------------------------

@app.route("/api/summary", methods=["GET"])
@require_user
def summary():
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        return bad("days muss eine Zahl sein.")
    if days not in ALLOWED_RANGES:
        return bad(f"days muss einer dieser Werte sein: {', '.join(map(str, ALLOWED_RANGES))}.")
    try:
        end = (
            parse_date(request.args["end"])
            if request.args.get("end")
            else user_today(g.user)
        )
    except ValueError as exc:
        return bad(str(exc))

    dates = date_range_iso(days, end)
    rows = g.conn.execute(
        "SELECT entry_date, COALESCE(SUM(kcal), 0) AS total, "
        "       COALESCE(SUM(protein), 0) AS protein, COUNT(*) AS entries "
        "FROM entries WHERE user_id = ? AND entry_date BETWEEN ? AND ? "
        "GROUP BY entry_date",
        (g.user["id"], dates[0], dates[-1]),
    ).fetchall()
    by_date = {r["entry_date"]: r for r in rows}
    goals = db.goals_by_date(g.conn, g.user["id"], dates)
    # Gewicht für das Gewichtsdiagramm im selben Zeitraum – ein Wert pro Tag,
    # Tage ohne Messung bleiben None statt 0.
    weights = {
        r["weigh_date"]: r["kg"]
        for r in g.conn.execute(
            "SELECT weigh_date, kg FROM weights "
            "WHERE user_id = ? AND weigh_date BETWEEN ? AND ?",
            (g.user["id"], dates[0], dates[-1]),
        )
    }

    result = []
    for date_iso in dates:
        row = by_date.get(date_iso)
        goal = goals[date_iso]
        result.append(
            {
                "date": date_iso,
                "total": round(row["total"], 1) if row else 0.0,
                "protein": round(row["protein"], 1) if row else 0.0,
                "entries": row["entries"] if row else 0,
                "kg": weights.get(date_iso),
                # Ziel und Richtung, die an diesem Tag galten – nicht die heutigen.
                "kcal_goal": goal["kcal_goal"],
                "protein_goal": goal["protein_goal"],
                "goal_direction": goal["goal_direction"],
            }
        )
    return jsonify(
        {
            "days": days,
            "end": end,
            "today": user_today(g.user),
            "calendar_date": today_iso(),
            "day_start_hour": day_start(g.user),
            "kcal_goal": g.user["kcal_goal"],
            "protein_goal": g.user["protein_goal"],
            "goal_direction": goal_direction(g.user),
            "series": result,
        }
    )


# Kalender: ein Jahr (53 volle Wochen) Tagessummen für die Heatmap. Nur Tage
# mit Einträgen, jeweils mit dem Ziel, das an dem Tag galt – wie viele Wochen
# davon zu sehen sind, entscheidet der Browser nach der Breite.
CALENDAR_DAYS = 53 * 7


@app.route("/api/calendar", methods=["GET"])
@require_user
def calendar():
    today = user_today(g.user)
    first = day_offset_iso(CALENDAR_DAYS - 1, today)
    rows = g.conn.execute(
        "SELECT entry_date, SUM(kcal) AS total, COUNT(*) AS entries FROM entries "
        "WHERE user_id = ? AND entry_date BETWEEN ? AND ? GROUP BY entry_date "
        "ORDER BY entry_date",
        (g.user["id"], first, today),
    ).fetchall()
    goals = db.goals_by_date(g.conn, g.user["id"], [r["entry_date"] for r in rows])
    days = [
        {
            "date": r["entry_date"],
            "total": round(r["total"], 1),
            "entries": r["entries"],
            "kcal_goal": goals[r["entry_date"]]["kcal_goal"],
            "goal_direction": goals[r["entry_date"]]["goal_direction"],
        }
        for r in rows
    ]
    return jsonify({"today": today, "first": first, "days": days})


# --------------------------------------------------------------------------
# Gewicht
# --------------------------------------------------------------------------

@app.route("/api/weights", methods=["GET"])
@require_user
def list_weights():
    rows = g.conn.execute(
        "SELECT id, weigh_date, kg FROM weights WHERE user_id = ? "
        "ORDER BY weigh_date DESC LIMIT 120",
        (g.user["id"],),
    ).fetchall()
    entries = [{"id": r["id"], "date": r["weigh_date"], "kg": r["kg"]} for r in rows]
    latest = entries[0] if entries else None
    trend = None
    if latest:
        cutoff = day_offset_iso(30, latest["date"])
        older = next((e for e in entries if e["date"] <= cutoff), entries[-1])
        if older["date"] != latest["date"]:
            trend = {
                "delta": round(latest["kg"] - older["kg"], 1),
                "from_date": older["date"],
            }
    return jsonify({"latest": latest, "trend": trend, "entries": entries})


@app.route("/api/weights", methods=["POST"])
@require_user
def add_weight():
    payload = body()
    try:
        kg = parse_number(payload.get("kg"), "Gewicht", 20, 400)
        weigh_date = (
            parse_date(payload["date"]) if payload.get("date") else user_today(g.user)
        )
    except ValueError as exc:
        return bad(str(exc))
    # Ein Wert pro Tag – ein zweiter Eintrag korrigiert den ersten.
    g.conn.execute(
        "INSERT INTO weights (user_id, weigh_date, kg, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (user_id, weigh_date) DO UPDATE SET kg = excluded.kg",
        (g.user["id"], weigh_date, kg, utc_now_iso()),
    )
    g.conn.commit()
    return jsonify({"ok": True, "date": weigh_date, "kg": kg}), 201


@app.route("/api/weights/<int:weight_id>", methods=["DELETE"])
@require_user
def delete_weight(weight_id: int):
    cur = g.conn.execute(
        "DELETE FROM weights WHERE id = ? AND user_id = ?", (weight_id, g.user["id"])
    )
    if not cur.rowcount:
        return bad("Eintrag nicht gefunden.", 404)
    g.conn.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# KI-Einschätzung
# --------------------------------------------------------------------------

def coach_inputs(conn, user) -> dict:
    # Nur abgeschlossene Tage: die 14 Tage enden gestern. Der laufende Tag
    # würde morgens als "400 kcal, weit unter dem Ziel" bewertet und den
    # Schnitt drücken. Außerdem bleibt der Hash darüber (siehe coach()) so den
    # ganzen Tag gleich – neue Einträge von heute lösen keinen KI-Aufruf aus,
    # die Einschätzung entsteht einmal am Tag oder auf Wunsch.
    start = day_start(user)
    today = user_today(user)
    dates = date_range_iso(14, day_offset_iso(1, today))
    rows = conn.execute(
        "SELECT entry_date, COALESCE(SUM(kcal), 0) AS total, "
        "       COALESCE(SUM(protein), 0) AS protein, COUNT(*) AS entries, "
        "       SUM(CASE WHEN protein IS NOT NULL THEN 1 ELSE 0 END) AS protein_rows "
        "FROM entries WHERE user_id = ? AND entry_date BETWEEN ? AND ? "
        "GROUP BY entry_date",
        (user["id"], dates[0], dates[-1]),
    ).fetchall()
    by_date = {r["entry_date"]: r for r in rows}
    goals = db.goals_by_date(conn, user["id"], dates)

    def day_entry(iso: str) -> dict:
        row = by_date.get(iso)
        goal = goals[iso]
        target = {
            "ziel_kcal": round(goal["kcal_goal"]) if goal["kcal_goal"] else None,
            "ziel_eiweiss_g": round(goal["protein_goal"]) if goal["protein_goal"] else None,
            "ziel_richtung": "abnehmen" if goal["goal_direction"] == "lose" else "zunehmen",
        }
        if not row:
            return {"datum": iso, "kcal": 0, "eiweiss_g": None, "eintraege": 0, **target}
        return {
            **target,
            "datum": iso,
            "kcal": round(row["total"]),
            # Ohne Eiweißangabe null statt 0 – sonst behauptet die
            # Einschätzung eine Null, die nie erfasst wurde.
            "eiweiss_g": round(row["protein"]) if row["protein_rows"] else None,
            "eintraege": row["entries"],
        }

    days = [day_entry(d) for d in dates]
    logged = [d for d in days if d["eintraege"] > 0]
    weights = conn.execute(
        "SELECT weigh_date, kg FROM weights WHERE user_id = ? AND weigh_date < ? "
        "ORDER BY weigh_date DESC LIMIT 10",
        (user["id"], today),
    ).fetchall()
    return {
        "ziel_kcal_pro_tag": user["kcal_goal"],
        "ziel_eiweiss_g_pro_tag": user["protein_goal"],
        # Steht auch im Systemprompt, gehört aber zusätzlich in die Daten: der
        # Hash darüber entscheidet, ob eine gespeicherte Einschätzung noch
        # gilt, und nach einem Wechsel der Richtung gilt sie nicht mehr.
        "ziel_richtung": "abnehmen" if goal_direction(user) == "lose" else "zunehmen",
        "tagesbeginn_uhr": start,
        "heute": today,
        "tage": days,
        "tage_mit_eintraegen": len(logged),
        "durchschnitt_kcal_erfasste_tage": (
            round(sum(d["kcal"] for d in logged) / len(logged)) if logged else 0
        ),
        "gewicht_verlauf": [
            {"datum": w["weigh_date"], "kg": w["kg"]} for w in reversed(weights)
        ],
    }


@app.route("/api/coach", methods=["GET"])
@app.route("/api/coach/refresh", methods=["POST"])
@require_user
def coach():
    # Nur der ausdrückliche Refresh umgeht den Cache – und der ist POST, damit
    # ihn niemand durch bloßes Verlinken auslösen und damit API-Kosten
    # verursachen kann.
    force = request.method == "POST"
    user = g.user
    if not user["kcal_goal"]:
        return jsonify(
            {
                "status": "no_goal",
                "headline": "Noch kein Tagesziel gesetzt",
                "message": (
                    "Leg in den Einstellungen ein Kalorienziel fest, dann bekommst "
                    "du hier eine Einschätzung, wie nah du dran bist."
                ),
                "tips": [],
                "cached": False,
            }
        )

    data = coach_inputs(g.conn, user)
    if data["tage_mit_eintraegen"] < 2:
        return jsonify(
            {
                "status": "no_data",
                "headline": "Noch zu wenig Daten",
                "message": (
                    "Trag ein paar Tage lang ein, was du isst – ab zwei erfassten "
                    "Tagen kann ich deinen Verlauf sinnvoll einschätzen."
                ),
                "tips": [],
                "cached": False,
            }
        )

    # Das Modell gehört mit in den Hash: nach einem Wechsel soll die nächste
    # Einschätzung vom neuen Modell kommen, nicht aus dem Zwischenspeicher.
    inputs_hash = sha256(
        json.dumps({"daten": data, "modell": ai_model(user)}, sort_keys=True,
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    day = user_today(user)
    if not force:
        cached = g.conn.execute(
            "SELECT payload FROM coach_cache WHERE user_id = ? AND day = ? "
            "AND inputs_hash = ?",
            (user["id"], day, inputs_hash),
        ).fetchone()
        if cached:
            payload = json.loads(cached["payload"])
            payload["cached"] = True
            return jsonify(payload)

    try:
        result = ai.coach_analysis(data, goal_direction(user), ai_model(user))
    except ai.AIError as exc:
        # Lieber die letzte Einschätzung zeigen als eine Fehlermeldung: im Free
        # Tier ist Gemini oft minutenlang überlastet, und eine Einschätzung von
        # vor ein paar Einträgen ist immer noch nützlicher als keine. Deshalb
        # löschen Änderungen an Einträgen, Gewicht oder Zielen den Cache auch
        # nicht mehr – ob er noch gilt, entscheidet allein inputs_hash.
        # Nach einem Wechsel der Zielrichtung wäre die alte Einschätzung
        # falsch herum bewertet – dann doch lieber die Fehlermeldung.
        fallback = g.conn.execute(
            "SELECT payload FROM coach_cache WHERE user_id = ? "
            "ORDER BY day DESC LIMIT 1",
            (user["id"],),
        ).fetchone()
        payload = json.loads(fallback["payload"]) if fallback else {}
        if payload.get("direction") != goal_direction(user):
            return bad(str(exc), 502)
        log.warning("Einschätzung fehlgeschlagen, zeige die letzte gespeicherte: %s", exc)
        payload["cached"] = True
        payload["stale"] = True
        payload["notice"] = str(exc)
        return jsonify(payload)

    result["direction"] = goal_direction(user)
    g.conn.execute(
        "INSERT INTO coach_cache (user_id, day, inputs_hash, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, day) DO UPDATE SET "
        "inputs_hash = excluded.inputs_hash, payload = excluded.payload, "
        "created_at = excluded.created_at",
        (user["id"], day, inputs_hash, json.dumps(result, ensure_ascii=False), utc_now_iso()),
    )
    g.conn.commit()
    result["cached"] = False
    return jsonify(result)


# --------------------------------------------------------------------------
# Ziele (im Code "habits", siehe habits.py)
# --------------------------------------------------------------------------

def own_habit(habit_id: int):
    return g.conn.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, g.user["id"])
    ).fetchone()


def can_check(habit, count_that_day: int) -> bool:
    # Tagesziele bis zum Ziel, Wochen- und Monatsziele einmal je Tag.
    limit = int(habit["target"]) if habit["period"] == "day" else 1
    return count_that_day < limit


def checkin_json(row) -> dict:
    return {"id": row["id"], "date": row["checkin_date"], "time": row["checkin_time"]}


def habit_json(conn, habit, today: str) -> dict:
    rows = conn.execute(
        "SELECT id, checkin_date, checkin_time FROM habit_checkins WHERE habit_id = ? "
        "ORDER BY checkin_date ASC, COALESCE(checkin_time, '') ASC, id ASC",
        (habit["id"],),
    ).fetchall()
    result = habits.stats(habit, [r["checkin_date"] for r in rows], today)
    current = result["current"]
    current["checkins"] = [
        checkin_json(r) for r in rows if current["start"] <= r["checkin_date"] <= current["end"]
    ]
    today_rows = [r for r in rows if r["checkin_date"] == today]
    result.update(
        {
            "id": habit["id"],
            "title": habit["title"],
            "icon": habit["icon"],
            "period": habit["period"],
            "target": int(habit["target"]),
            "start_date": habit["start_date"],
            "today": today,
            "today_count": len(today_rows),
            "today_checkins": [r["id"] for r in today_rows],
            "can_check_today": can_check(habit, len(today_rows)),
        }
    )
    return result


def parse_habit(payload: dict, existing=None) -> dict:
    """Prüft Name, Zeitraum, Anzahl und Symbol. Beim Ändern nur, was kommt."""
    fields = {}
    if existing is None or "title" in payload:
        title = " ".join(str(payload.get("title") or "").split())
        if not title:
            raise ValueError("Bitte gib dem Ziel einen Namen.")
        if len(title) > habits.TITLE_MAX:
            raise ValueError(f"Der Name ist zu lang (höchstens {habits.TITLE_MAX} Zeichen).")
        fields["title"] = title
    if existing is None or "period" in payload:
        period = payload.get("period")
        if period not in habits.PERIODS:
            raise ValueError("Zeitraum muss Tag, Woche oder Monat sein.")
        fields["period"] = period
    period = fields.get("period") or existing["period"]
    if existing is None or "target" in payload or "period" in payload:
        raw = payload.get("target", existing["target"] if existing is not None else None)
        top = habits.MAX_TARGET[period]
        target = parse_number(raw, "Anzahl", 1, top)
        if target != int(target):
            raise ValueError("Die Anzahl muss eine ganze Zahl sein.")
        fields["target"] = int(target)
    if existing is None or "icon" in payload:
        icon = payload.get("icon") or "star"
        if icon not in habits.ICONS:
            raise ValueError("Unbekanntes Symbol.")
        fields["icon"] = icon
    return fields


@app.route("/api/habits", methods=["GET"])
@require_user
def list_habits():
    today = user_today(g.user)
    rows = g.conn.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY sort_order ASC, id ASC",
        (g.user["id"],),
    ).fetchall()
    return jsonify({"today": today, "habits": [habit_json(g.conn, r, today) for r in rows]})


@app.route("/api/habits", methods=["POST"])
@require_user
def create_habit():
    try:
        fields = parse_habit(body())
    except ValueError as exc:
        return bad(str(exc))
    count = g.conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(MAX(sort_order), 0) AS last FROM habits WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()
    if count["n"] >= habits.MAX_HABITS:
        return bad(f"Mehr als {habits.MAX_HABITS} Ziele gehen nicht.")
    today = user_today(g.user)
    cur = g.conn.execute(
        "INSERT INTO habits (user_id, title, icon, period, target, start_date, sort_order, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            g.user["id"], fields["title"], fields["icon"], fields["period"], fields["target"],
            today, count["last"] + 1, utc_now_iso(),
        ),
    )
    g.conn.commit()
    return jsonify(habit_json(g.conn, own_habit(cur.lastrowid), today)), 201


@app.route("/api/habits/<int:habit_id>", methods=["GET"])
@require_user
def get_habit(habit_id: int):
    habit = own_habit(habit_id)
    if not habit:
        return bad("Ziel nicht gefunden.", 404)
    today = user_today(g.user)
    try:
        end = parse_date(request.args["to"], "Ende") if request.args.get("to") else today
        start = (
            parse_date(request.args["from"], "Beginn")
            if request.args.get("from")
            else day_offset_iso(26 * 7, end)
        )
    except ValueError as exc:
        return bad(str(exc))
    if start > end:
        return bad("Der Beginn liegt nach dem Ende.")
    if day_offset_iso(400, end) > start:
        return bad("Höchstens 400 Tage auf einmal.")
    days = {
        r["checkin_date"]: r["n"]
        for r in g.conn.execute(
            "SELECT checkin_date, COUNT(*) AS n FROM habit_checkins "
            "WHERE habit_id = ? AND checkin_date BETWEEN ? AND ? GROUP BY checkin_date",
            (habit_id, start, end),
        )
    }
    dates = [
        r["checkin_date"]
        for r in g.conn.execute(
            "SELECT checkin_date FROM habit_checkins WHERE habit_id = ? AND checkin_date BETWEEN ? AND ?",
            (habit_id, day_offset_iso(40, start), end),
        )
    ]
    result = habit_json(g.conn, habit, today)
    result["history"] = {
        "from": start,
        "to": end,
        "days": days,
        "periods": habits.met_periods(dates, habit, start, min(end, today)),
    }
    return jsonify(result)


@app.route("/api/habits/<int:habit_id>", methods=["PATCH"])
@require_user
def update_habit(habit_id: int):
    habit = own_habit(habit_id)
    if not habit:
        return bad("Ziel nicht gefunden.", 404)
    try:
        fields = parse_habit(body(), habit)
    except ValueError as exc:
        return bad(str(exc))
    if fields:
        sets = ", ".join(f"{name} = ?" for name in fields)
        g.conn.execute(
            f"UPDATE habits SET {sets} WHERE id = ? AND user_id = ?",
            (*fields.values(), habit_id, g.user["id"]),
        )
        g.conn.commit()
    return jsonify(habit_json(g.conn, own_habit(habit_id), user_today(g.user)))


@app.route("/api/habits/<int:habit_id>", methods=["DELETE"])
@require_user
def delete_habit(habit_id: int):
    if not own_habit(habit_id):
        return bad("Ziel nicht gefunden.", 404)
    g.conn.execute("DELETE FROM habit_checkins WHERE habit_id = ?", (habit_id,))
    g.conn.execute("DELETE FROM habits WHERE id = ? AND user_id = ?", (habit_id, g.user["id"]))
    g.conn.commit()
    return jsonify({"ok": True})


@app.route("/api/habits/<int:habit_id>/checkins", methods=["GET"])
@require_user
def list_checkins(habit_id: int):
    if not own_habit(habit_id):
        return bad("Ziel nicht gefunden.", 404)
    try:
        day = parse_date(request.args.get("date") or user_today(g.user))
    except ValueError as exc:
        return bad(str(exc))
    rows = g.conn.execute(
        "SELECT id, checkin_date, checkin_time FROM habit_checkins "
        "WHERE habit_id = ? AND checkin_date = ? ORDER BY COALESCE(checkin_time, ''), id",
        (habit_id, day),
    ).fetchall()
    return jsonify({"date": day, "checkins": [checkin_json(r) for r in rows]})


@app.route("/api/habits/<int:habit_id>/checkins", methods=["POST"])
@require_user
def add_checkin(habit_id: int):
    habit = own_habit(habit_id)
    if not habit:
        return bad("Ziel nicht gefunden.", 404)
    payload = body()
    today = user_today(g.user)
    try:
        day = parse_date(payload["date"]) if payload.get("date") else today
    except ValueError as exc:
        return bad(str(exc))
    if day > today:
        return bad("Für künftige Tage lässt sich nichts eintragen.")
    count = g.conn.execute(
        "SELECT COUNT(*) AS n FROM habit_checkins WHERE habit_id = ? AND checkin_date = ?",
        (habit_id, day),
    ).fetchone()["n"]
    if not can_check(habit, count):
        if habit["period"] == "day":
            return bad("Für diesen Tag ist das Ziel schon erreicht.", 409)
        return bad(
            "An diesem Tag ist schon eingetragen – bei Wochen- und Monatszielen zählt jeder Tag einmal.",
            409,
        )
    before = habit_json(g.conn, habit, today)
    cur = g.conn.execute(
        "INSERT INTO habit_checkins (habit_id, user_id, checkin_date, checkin_time, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (habit_id, g.user["id"], day, local_time_hhmm() if day == today else None, utc_now_iso()),
    )
    g.conn.commit()
    after = habit_json(g.conn, habit, today)
    # "Geschafft" nur für den Eintrag, der den laufenden Zeitraum voll macht –
    # darauf reagiert das Frontend mit Konfetti (bei Wochen und Monaten).
    in_current = before["current"]["start"] <= day <= before["current"]["end"]
    completed = in_current and not before["current"]["met"] and after["current"]["met"]
    return jsonify(
        {
            "habit": after,
            "checkin": {"id": cur.lastrowid, "date": day},
            "completed": completed,
            "milestone": after["streak"] if completed and after["milestone_hit"] else None,
            "record": completed and before["best"] > 0 and after["streak"] > before["best"],
        }
    ), 201


@app.route("/api/habits/<int:habit_id>/checkins/<int:checkin_id>", methods=["DELETE"])
@require_user
def delete_checkin(habit_id: int, checkin_id: int):
    habit = own_habit(habit_id)
    if not habit:
        return bad("Ziel nicht gefunden.", 404)
    cur = g.conn.execute(
        "DELETE FROM habit_checkins WHERE id = ? AND habit_id = ? AND user_id = ?",
        (checkin_id, habit_id, g.user["id"]),
    )
    if not cur.rowcount:
        return bad("Eintrag nicht gefunden.", 404)
    g.conn.commit()
    return jsonify({"habit": habit_json(g.conn, habit, user_today(g.user))})


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

@app.route("/api/export.csv", methods=["GET"])
@require_user
def export_csv():
    rows = g.conn.execute(
        'SELECT entry_date, entry_time, "desc", kcal, protein FROM entries '
        "WHERE user_id = ? ORDER BY entry_date ASC, entry_time ASC, id ASC",
        (g.user["id"],),
    ).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Datum", "Uhrzeit", "Beschreibung", "kcal", "Eiweiss_g"])
    for row in rows:
        writer.writerow(
            [
                row["entry_date"],
                row["entry_time"],
                row["desc"],
                round(row["kcal"], 1),
                "" if row["protein"] is None else round(row["protein"], 1),
            ]
        )
    return Response(
        # BOM, damit Excel die Umlaute richtig erkennt.
        "﻿" + buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="kalorien-{today_iso()}.csv"'
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
