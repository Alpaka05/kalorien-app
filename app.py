import os
import sqlite3
import json
import re
from datetime import date, timedelta
from flask import Flask, request, jsonify, send_from_directory
import requests

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data", "kalorien.db")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

app = Flask(__name__, static_folder="static", static_url_path="")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            desc TEXT NOT NULL,
            kcal REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def estimate_kcal(desc):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 200,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Schätze die Kalorien (kcal) für folgende Mahlzeit/Getränk "
                        "realistisch anhand üblicher Portionsgrößen. Antworte NUR mit "
                        'JSON, kein weiterer Text, kein Markdown: {"kcal": <Zahl>, '
                        '"normalized": "<kurze Beschreibung auf Deutsch>"}. Eingabe: '
                        + desc
                    ),
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    text_block = next((b for b in data.get("content", []) if b.get("type") == "text"), None)
    if not text_block:
        raise RuntimeError("Keine Antwort erhalten")
    clean = re.sub(r"```json|```", "", text_block["text"]).strip()
    parsed = json.loads(clean)
    if not isinstance(parsed.get("kcal"), (int, float)):
        raise RuntimeError("Ungültige Antwort")
    return parsed


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/entries", methods=["GET"])
def list_entries():
    entry_date = request.args.get("date", date.today().isoformat())
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM entries WHERE entry_date = ? ORDER BY id ASC", (entry_date,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/entries", methods=["POST"])
def add_entry():
    body = request.get_json(force=True) or {}
    desc = (body.get("desc") or "").strip()
    if not desc:
        return jsonify({"error": "Bitte gib ein, was du gegessen oder getrunken hast."}), 400
    try:
        result = estimate_kcal(desc)
    except Exception:
        return jsonify({"error": "Schätzung fehlgeschlagen. Bitte nochmal versuchen."}), 502

    now = date.today().isoformat()
    from datetime import datetime

    entry_time = datetime.now().strftime("%H:%M")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO entries (entry_date, entry_time, desc, kcal, created_at) VALUES (?, ?, ?, ?, ?)",
        (now, entry_time, result.get("normalized") or desc, float(result["kcal"]), datetime.utcnow().isoformat()),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    conn = get_db()
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/summary", methods=["GET"])
def summary():
    days = int(request.args.get("days", 7))
    conn = get_db()
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        row = conn.execute(
            "SELECT COALESCE(SUM(kcal), 0) as total FROM entries WHERE entry_date = ?", (d,)
        ).fetchone()
        result.append({"date": d, "total": row["total"]})
    conn.close()
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
