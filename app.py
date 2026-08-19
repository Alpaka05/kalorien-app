"""Kalorien-Tagebuch – Flask-Backend.

Alle Daten sind pro Konto getrennt; jede API-Route filtert konsequent nach
`user_id` aus der Session.
"""

import csv
import functools
import io
import ipaddress
import json
import logging
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
    send_from_directory,
)

import ai
import auth
import db
import mailer
from timeutil import (
    date_range_iso,
    day_offset_iso,
    local_time_hhmm,
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

app = Flask(__name__, static_folder="static", static_url_path="")
db.init_db()


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


def entry_json(row) -> dict:
    return {
        "id": row["id"],
        "date": row["entry_date"],
        "time": row["entry_time"],
        "desc": row["desc"],
        "kcal": row["kcal"],
        "protein": row["protein"],
    }


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
    return send_from_directory(app.static_folder, "index.html")


@app.route("/login")
def login_page():
    return send_from_directory(app.static_folder, "login.html")


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
            "mail_configured": mailer.is_configured(),
        }
    )


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
    except ValueError as exc:
        return bad(str(exc))

    if fields:
        values.append(g.user["id"])
        g.conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        # Die Einschätzung basiert auf dem Ziel und ist damit veraltet.
        g.conn.execute("DELETE FROM coach_cache WHERE user_id = ?", (g.user["id"],))
        g.conn.commit()

    row = g.conn.execute(
        "SELECT email, display_name, kcal_goal, protein_goal FROM users WHERE id = ?",
        (g.user["id"],),
    ).fetchone()
    return jsonify(dict(row))


# --------------------------------------------------------------------------
# Einträge
# --------------------------------------------------------------------------

@app.route("/api/entries", methods=["GET"])
@require_user
def list_entries():
    try:
        entry_date = parse_date(request.args.get("date") or today_iso())
    except ValueError as exc:
        return bad(str(exc))
    rows = g.conn.execute(
        'SELECT id, entry_date, entry_time, "desc", kcal, protein FROM entries '
        "WHERE user_id = ? AND entry_date = ? ORDER BY entry_time ASC, id ASC",
        (g.user["id"], entry_date),
    ).fetchall()
    return jsonify(
        {"date": entry_date, "entries": [entry_json(r) for r in rows]}
    )


@app.route("/api/entries", methods=["POST"])
@require_user
def add_entry():
    payload = body()
    description = (payload.get("desc") or "").strip()
    if not description:
        return bad("Bitte gib ein, was du gegessen oder getrunken hast.")
    if len(description) > 500:
        return bad("Die Beschreibung ist zu lang (maximal 500 Zeichen).")

    try:
        entry_date = parse_date(payload["date"]) if payload.get("date") else today_iso()
        entry_time = parse_time(payload["time"]) if payload.get("time") else local_time_hhmm()
        # Schnell-Eintrag aus den Favoriten: Werte sind bekannt, die KI wird
        # nicht gebraucht (spart Zeit und API-Kosten).
        if payload.get("kcal") is not None:
            kcal = parse_number(payload["kcal"], "Kalorien", 0, 20000)
            protein = (
                parse_number(payload["protein"], "Eiweiß", 0, 1000)
                if payload.get("protein") is not None
                else None
            )
            normalized = description
        else:
            estimate = ai.estimate_meal(description)
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
    g.conn.execute("DELETE FROM coach_cache WHERE user_id = ?", (g.user["id"],))
    g.conn.commit()
    row = g.conn.execute(
        'SELECT id, entry_date, entry_time, "desc", kcal, protein FROM entries WHERE id = ?',
        (cur.lastrowid,),
    ).fetchone()
    return jsonify(entry_json(row)), 201


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
            values.append(parse_date(payload["date"]))
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
    g.conn.execute("DELETE FROM coach_cache WHERE user_id = ?", (g.user["id"],))
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
    g.conn.execute("DELETE FROM coach_cache WHERE user_id = ?", (g.user["id"],))
    g.conn.commit()
    return jsonify({"ok": True})


@app.route("/api/favorites", methods=["GET"])
@require_user
def favorites():
    """Häufig eingetragene Mahlzeiten der letzten 60 Tage für den Schnell-Eintrag."""
    rows = g.conn.execute(
        'SELECT "desc" AS desc, COUNT(*) AS uses, '
        "       ROUND(AVG(kcal)) AS kcal, ROUND(AVG(protein)) AS protein "
        "FROM entries WHERE user_id = ? AND entry_date >= ? "
        'GROUP BY LOWER("desc") HAVING COUNT(*) >= 2 '
        "ORDER BY uses DESC, MAX(id) DESC LIMIT 6",
        (g.user["id"], day_offset_iso(60)),
    ).fetchall()
    return jsonify(
        [
            {
                "desc": r["desc"],
                "kcal": r["kcal"],
                "protein": r["protein"],
                "uses": r["uses"],
            }
            for r in rows
        ]
    )


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
        end = parse_date(request.args["end"]) if request.args.get("end") else today_iso()
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

    result = []
    for date_iso in dates:
        row = by_date.get(date_iso)
        result.append(
            {
                "date": date_iso,
                "total": round(row["total"], 1) if row else 0.0,
                "protein": round(row["protein"], 1) if row else 0.0,
                "entries": row["entries"] if row else 0,
            }
        )
    return jsonify(
        {
            "days": days,
            "end": end,
            "today": today_iso(),
            "kcal_goal": g.user["kcal_goal"],
            "protein_goal": g.user["protein_goal"],
            "series": result,
        }
    )


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
        weigh_date = parse_date(payload["date"]) if payload.get("date") else today_iso()
    except ValueError as exc:
        return bad(str(exc))
    # Ein Wert pro Tag – ein zweiter Eintrag korrigiert den ersten.
    g.conn.execute(
        "INSERT INTO weights (user_id, weigh_date, kg, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (user_id, weigh_date) DO UPDATE SET kg = excluded.kg",
        (g.user["id"], weigh_date, kg, utc_now_iso()),
    )
    g.conn.execute("DELETE FROM coach_cache WHERE user_id = ?", (g.user["id"],))
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
    dates = date_range_iso(14)
    rows = conn.execute(
        "SELECT entry_date, COALESCE(SUM(kcal), 0) AS total, "
        "       COALESCE(SUM(protein), 0) AS protein, COUNT(*) AS entries, "
        "       SUM(CASE WHEN protein IS NOT NULL THEN 1 ELSE 0 END) AS protein_rows "
        "FROM entries WHERE user_id = ? AND entry_date BETWEEN ? AND ? "
        "GROUP BY entry_date",
        (user["id"], dates[0], dates[-1]),
    ).fetchall()
    by_date = {r["entry_date"]: r for r in rows}

    def day_entry(iso: str) -> dict:
        row = by_date.get(iso)
        if not row:
            return {"datum": iso, "kcal": 0, "eiweiss_g": None, "eintraege": 0}
        return {
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
        "SELECT weigh_date, kg FROM weights WHERE user_id = ? "
        "ORDER BY weigh_date DESC LIMIT 10",
        (user["id"],),
    ).fetchall()
    return {
        "ziel_kcal_pro_tag": user["kcal_goal"],
        "ziel_eiweiss_g_pro_tag": user["protein_goal"],
        "heute": today_iso(),
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

    inputs_hash = sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    day = today_iso()
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
        result = ai.coach_analysis(data)
    except ai.AIError as exc:
        return bad(str(exc), 502)

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
