"""Gemini-API-Aufrufe: Kalorienschätzung und Ziel-Einschätzung.

Beide Aufrufe nutzen Structured Output (`responseJsonSchema`), damit die
Antwort garantiert gültiges JSON nach unserem Schema ist – kein Parsen von
Freitext, kein Aufräumen von Markdown-Codeblöcken.

Die Gemini-API wird direkt über REST angesprochen (nur Standardbibliothek).
Das spart eine Abhängigkeit und reicht für zwei Aufrufe völlig aus.
"""

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request

log = logging.getLogger("kalorien.ai")

# Gemini Flash als Standard: im Free Tier von Google AI Studio kostenlos und
# für Kalorienschätzungen mehr als ausreichend. Über GEMINI_MODEL umstellbar,
# z. B. auf gemini-2.5-flash-lite, wenn das Tageslimit des Free Tiers knapp
# wird (Flash-Lite hat dort das großzügigste Kontingent).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Gemini-Modelle denken standardmäßig auf Stufe "medium" vor jeder Antwort.
# Für eine Kalorienschätzung ist das unnötig und kostet Sekunden, deshalb wird
# die Denkstufe pro Aufruf gesetzt (derzeit "low" für beide Aufrufe).
# Nicht jedes Modell kennt den Parameter; lehnt Gemini ihn ab, wird der Aufruf
# einmal ohne ihn wiederholt und der Parameter danach nicht mehr gesendet.
# Mit AI_THINKING=off lässt er sich von vornherein abschalten.
_thinking_enabled = os.environ.get("AI_THINKING", "").strip().lower() != "off"

# Zeitbudget: Die App muss auf jeden Fall selbst antworten, bevor der Proxy
# davor die Verbindung kappt – Nginx tut das standardmäßig nach 60 Sekunden,
# ein Cloudflare-Tunnel nach 100. Sonst bekommt das Frontend eine HTML-Seite
# statt JSON und kann nur "Da ist etwas schiefgelaufen" anzeigen. TOTAL_DEADLINE
# gilt deshalb für alle Versuche zusammen; ein zweiter Versuch bekommt nur die
# Restzeit und findet gar nicht statt, wenn sie zu knapp ist.
REQUEST_TIMEOUT = 30.0
TOTAL_DEADLINE = 50.0
MIN_RETRY_TIME = 8.0
MAX_RETRIES = 1


class AIError(Exception):
    """Fehler, dessen Text der Nutzerin gezeigt werden darf."""


class _BadRequest(Exception):
    """HTTP 400 von Gemini; der Aufrufer entscheidet, ob ein Rückfall möglich ist."""


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise AIError("GEMINI_API_KEY ist nicht gesetzt.")
    return key


def _error_message(exc: urllib.error.HTTPError) -> str:
    """Liest die Fehlermeldung aus dem JSON-Fehlerkörper der Gemini-API."""
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        err = payload.get("error") or {}
        parts = [str(err.get("status") or ""), str(err.get("message") or "")]
        return " ".join(p for p in parts if p) or str(exc)
    except Exception:
        return str(exc)


def _post(url: str, body: dict, key: str, deadline: float) -> dict:
    """Ein HTTP-POST an die Gemini-API; wiederholt bei Limit- und Serverfehlern.

    `deadline` ist ein Zeitpunkt (time.monotonic), bis zu dem die Antwort da sein
    muss – über alle Versuche hinweg.
    """
    data = json.dumps(body).encode("utf-8")
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        remaining = deadline - time.monotonic()
        if attempt > 0 and remaining < MIN_RETRY_TIME:
            log.warning("Keine Zeit mehr für einen weiteren Gemini-Versuch")
            break
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            timeout = max(1.0, min(REQUEST_TIMEOUT, remaining))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = _error_message(exc)
            status = exc.code
            if status in (401, 403) or (status == 400 and "API_KEY" in detail.upper()):
                # Ungültiger Key – Wiederholen hilft nicht.
                log.error("Gemini akzeptiert den API-Key nicht (%s): %s", status, detail)
                raise AIError("Der Gemini-API-Key wird nicht akzeptiert.") from exc
            if status == 400:
                raise _BadRequest(detail) from exc
            if status == 404:
                log.error("Gemini kennt das Modell %s nicht: %s", GEMINI_MODEL, detail)
                raise AIError(f"Das Modell {GEMINI_MODEL} ist unbekannt.") from exc
            # 429 (Limit) und 5xx: einmal wiederholen, dann aufgeben.
            log.warning("Gemini-Fehler %s (Versuch %d): %s", status, attempt + 1, detail)
            last_exc = exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            if _is_timeout(exc):
                log.warning("Gemini antwortet nicht rechtzeitig (Versuch %d)", attempt + 1)
            else:
                log.warning("Keine Verbindung zu Gemini (Versuch %d): %s", attempt + 1, exc)
            last_exc = exc

    if isinstance(last_exc, urllib.error.HTTPError):
        if last_exc.code == 429:
            raise AIError(
                "Gemini-Limit erreicht. Bitte gleich nochmal versuchen."
            ) from last_exc
        raise AIError("Die KI-Anfrage ist fehlgeschlagen.") from last_exc
    if last_exc is not None and _is_timeout(last_exc):
        raise AIError(
            "Gemini hat nicht rechtzeitig geantwortet. Bitte nochmal versuchen."
        ) from last_exc
    raise AIError("Keine Verbindung zur Gemini-API.") from last_exc


def _is_timeout(exc: Exception) -> bool:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(
        exc.reason, (socket.timeout, TimeoutError)
    )


def _build_body(prompt: str, schema: dict, max_tokens: int, thinking: str | None) -> dict:
    generation_config: dict = {
        "responseMimeType": "application/json",
        # responseJsonSchema nimmt normales JSON Schema an und behält die
        # Reihenfolge der Felder bei – wichtig, weil unser Mahlzeit-Schema
        # darauf baut, dass die Bestandteile vor der Summe erzeugt werden.
        "responseJsonSchema": schema,
        "maxOutputTokens": max_tokens,
        "temperature": 0.2,
    }
    if thinking:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking}
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }


def _json_call(prompt: str, schema: dict, max_tokens: int, thinking: str) -> dict:
    global _thinking_enabled
    key = _api_key()
    url = GEMINI_ENDPOINT.format(model=GEMINI_MODEL)
    deadline = time.monotonic() + TOTAL_DEADLINE
    try:
        try:
            response = _post(
                url,
                _build_body(prompt, schema, max_tokens, thinking if _thinking_enabled else None),
                key,
                deadline,
            )
        except _BadRequest as exc:
            if not _thinking_enabled:
                raise
            # Vermutlich kennt das Modell die Denkstufe nicht: einmal ohne
            # versuchen und den Parameter für den Rest der Laufzeit weglassen.
            log.warning(
                "Gemini lehnt die Anfrage mit Denkstufe ab (Modell %s): %s – "
                "wiederhole ohne thinkingConfig",
                GEMINI_MODEL, exc,
            )
            _thinking_enabled = False
            response = _post(url, _build_body(prompt, schema, max_tokens, None), key, deadline)
    except _BadRequest as exc:
        log.error("Gemini lehnt die Anfrage ab (Modell %s): %s", GEMINI_MODEL, exc)
        raise AIError(
            f"Die Anfrage wurde abgelehnt. Passt GEMINI_MODEL ({GEMINI_MODEL})?"
        ) from exc
    except AIError:
        raise
    except Exception as exc:  # Unerwartetes darf keine 500-Seite erzeugen
        log.exception("Unerwarteter Fehler beim Gemini-Aufruf")
        raise AIError("Die KI-Anfrage ist fehlgeschlagen.") from exc

    # Wurde schon der Prompt blockiert, gibt es keine Kandidaten.
    feedback = response.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        log.error("Gemini hat den Prompt blockiert: %s", feedback.get("blockReason"))
        raise AIError("Die KI hat diese Anfrage abgelehnt.")

    candidates = response.get("candidates") or []
    if not candidates:
        raise AIError("Von der KI kam keine verwertbare Antwort.")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    if finish == "MAX_TOKENS":
        # Bei Modellen mit Thinking teilen sich Denk- und Antworttokens das
        # Budget; hier wurde es ausgeschöpft.
        log.error("maxOutputTokens (%d) erschöpft – Budget in ai.py erhöhen", max_tokens)
        raise AIError("Die Antwort wurde abgeschnitten. Bitte nochmal versuchen.")
    if finish in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        log.error("Gemini hat die Antwort abgebrochen: %s", finish)
        raise AIError("Die KI hat diese Anfrage abgelehnt.")

    parts = (candidate.get("content") or {}).get("parts") or []
    # Denk-Teile (thought=true) überspringen, nur die eigentliche Antwort nehmen.
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise AIError("Von der KI kam keine verwertbare Antwort.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("Die Antwort der KI war nicht lesbar.") from exc


# --------------------------------------------------------------------------
# Kalorienschätzung
# --------------------------------------------------------------------------

# Die Bestandteile stehen absichtlich als erstes Feld im Schema: Structured
# Outputs erzeugt die Felder in dieser Reihenfolge, das Modell zerlegt die
# Mahlzeit also erst und nennt die Summe danach. Vorher gab es nur das
# Ergebnisfeld – die Schätzung musste ohne jeden Zwischenschritt entstehen, und
# genau dabei geht bei zusammengesetzten Gerichten am meisten schief.
MEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "description": (
                "Jeder Bestandteil einzeln, auch wenn es nur einer ist. Keine "
                "Sammelposten und keine Gesamtgerichte neben ihren Einzelteilen."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "bestandteil": {
                        "type": "string",
                        "description": "Name des Bestandteils auf Deutsch.",
                    },
                    "menge": {
                        "type": "string",
                        "description": (
                            "Angenommene Menge mit Einheit, z. B. '2 Scheiben (50 g)' "
                            "oder '250 ml'."
                        ),
                    },
                    "kcal": {
                        "type": "number",
                        "description": "Kilokalorien dieses Bestandteils.",
                    },
                    "protein_g": {
                        "type": "number",
                        "description": "Eiweiß dieses Bestandteils in Gramm.",
                    },
                },
                "required": ["bestandteil", "menge", "kcal", "protein_g"],
                "additionalProperties": False,
            },
        },
        "normalized": {
            "type": "string",
            "description": (
                "Kurze deutsche Beschreibung der Mahlzeit mit den angenommenen "
                "Mengen, damit die Annahme nachvollziehbar bleibt."
            ),
        },
        "kcal": {"type": "number", "description": "Summe der Bestandteile."},
        "protein_g": {"type": "number", "description": "Eiweißsumme der Bestandteile."},
    },
    "required": ["components", "normalized", "kcal", "protein_g"],
    "additionalProperties": False,
}

MEAL_PROMPT = (
    "Schätze für die folgende Angabe die Kilokalorien und das Eiweiß in Gramm.\n\n"
    "Gehe dabei so vor:\n"
    "1. Zerlege die Angabe in ihre Bestandteile. Auch eine einzelne Speise ist "
    "ein Bestandteil.\n"
    "2. Lege für jeden Bestandteil eine konkrete Menge mit Einheit fest. Ist "
    "keine Menge genannt, nimm eine übliche Portion an und nenne sie.\n"
    "3. Schätze kcal und Eiweiß je Bestandteil.\n"
    "4. Nenne in `kcal` und `protein_g` die Summe der Bestandteile.\n\n"
    "Zähle nichts doppelt: entweder das fertige Gericht als einen Bestandteil "
    "oder seine Einzelteile, nicht beides. "
)

# Eine Schätzung liegt immer irgendwo daneben; die Frage ist nur, in welche
# Richtung. Der Fehler soll dorthin fallen, wo er der Person nichts vormacht:
# beim Zunehmen lässt eine zu hohe Schätzung das Tagesziel als erreicht
# erscheinen, beim Abnehmen lässt eine zu niedrige es als eingehalten
# erscheinen. Die Vorgabe dreht sich deshalb mit der Zielrichtung.
MEAL_UNCERTAINTY = {
    "gain": (
        "Bei Unsicherheit schätze eher knapp als groß – eine zu hohe Schätzung "
        "lässt ein Tagesziel als erreicht erscheinen, obwohl es das nicht ist."
    ),
    "lose": (
        "Bei Unsicherheit schätze eher großzügig als knapp – eine zu niedrige "
        "Schätzung lässt ein Tagesziel als eingehalten erscheinen, obwohl es "
        "das nicht ist."
    ),
}


def estimate_meal(description: str, direction: str = "gain") -> dict:
    """Schätzt kcal und Eiweiß für eine Freitext-Angabe."""
    uncertainty = MEAL_UNCERTAINTY.get(direction, MEAL_UNCERTAINTY["gain"])
    result = _json_call(
        MEAL_PROMPT + uncertainty + "\n\nAngabe: " + description,
        MEAL_SCHEMA,
        # Großzügig, weil Denk- und Antworttokens sich das Budget teilen.
        max_tokens=8192,
        thinking="low",
    )

    # Maßgeblich ist die Summe der Bestandteile, nicht die Zahl, die das Modell
    # daneben nennt: nur die Summe passt garantiert zu der Aufschlüsselung, aus
    # der sie entstanden ist. Weicht die eigene Summe des Modells stark ab, ist
    # das ein Hinweis auf Doppelzählung und landet im Log.
    components = [c for c in (result.get("components") or []) if isinstance(c, dict)]
    kcal = _sum_components(components, "kcal")
    protein = _sum_components(components, "protein_g")
    stated = result.get("kcal")
    if kcal is None:
        # Ohne brauchbare Bestandteile bleibt nur die genannte Summe.
        kcal, protein = stated, result.get("protein_g")
    elif isinstance(stated, (int, float)) and kcal > 0 and abs(stated - kcal) / kcal > 0.15:
        log.warning(
            "Schätzung uneinheitlich für %r: Bestandteile ergeben %.0f kcal, "
            "genannt wurden %.0f kcal",
            description[:80], kcal, stated,
        )

    if not isinstance(kcal, (int, float)) or not 0 <= kcal <= 20000:
        raise AIError("Die Schätzung war nicht plausibel. Bitte präziser beschreiben.")
    # Auch geschätzte Werte werden begrenzt, damit ein Ausrutscher der KI keine
    # unsinnigen Zahlen in die Statistik und in spätere Auswertungen trägt.
    valid_protein = isinstance(protein, (int, float)) and 0 <= protein <= 1000
    return {
        "normalized": (result.get("normalized") or description).strip()[:300],
        "kcal": float(kcal),
        "protein": float(protein) if valid_protein else None,
        # Noch nicht gespeichert, aber für das Log und einen späteren
        # Aufschlüsselungs-Nachweis in der Oberfläche schon vorhanden.
        "components": components,
    }


def _sum_components(components: list, key: str) -> float | None:
    """Summiert ein Zahlenfeld über die Bestandteile; None, wenn nichts brauchbar ist.

    Unbrauchbare Posten (fehlendes Feld, keine Zahl, negativ) werden
    übersprungen: eine Teilsumme ist immer noch besser als keine Angabe, und die
    Abweichungsprüfung beim Aufrufer schlägt an, wenn dabei zu viel wegfällt.
    """
    values = [c.get(key) for c in components]
    usable = [float(v) for v in values if isinstance(v, (int, float)) and v >= 0]
    return sum(usable) if usable else None


# --------------------------------------------------------------------------
# Ziel-Einschätzung ("Coach")
# --------------------------------------------------------------------------

COACH_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["on_track", "slightly_behind", "behind", "above_goal", "no_data"],
            "description": (
                "Wo die letzten Tage zum Tagesziel liegen – die Lage, nicht die "
                "Bewertung: on_track im Zielkorridor, above_goal darüber, "
                "slightly_behind knapp darunter, behind deutlich darunter. Ob "
                "das gut oder schlecht ist, hängt an der Zielrichtung und "
                "gehört in headline und message, nicht hierher."
            ),
        },
        "headline": {
            "type": "string",
            "description": "Ein Satz als Überschrift, maximal 70 Zeichen.",
        },
        "message": {
            "type": "string",
            "description": "Zwei bis vier Sätze Einschätzung mit Bezug auf konkrete Zahlen.",
        },
        "tips": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ein bis drei kurze, konkrete Vorschläge.",
        },
    },
    "required": ["status", "headline", "message", "tips"],
    "additionalProperties": False,
}

# Die Zielrichtung entscheidet, welche Abweichung ein Problem ist. Alles
# andere – Tonfall, Umgang mit Lücken, Grenzen der Auskunft – gilt für beide
# Richtungen und steht deshalb nur einmal in COACH_RULES.
COACH_GOAL = {
    "gain": (
        "Das Ziel der Person ist ZUZUNEHMEN: sie muss ihr Tagesziel erreichen "
        "oder leicht überschreiten, zu wenig ist das Problem, nicht zu viel. "
    ),
    "lose": (
        "Das Ziel der Person ist ABZUNEHMEN: das Tagesziel ist eine Obergrenze, "
        "unter der sie bleiben will, zu viel ist das Problem, nicht zu wenig. "
        "Lobe aber nicht, wer deutlich darunter liegt: zu wenig zu essen hält "
        "niemand lange durch und kostet eher Muskeln als Fett. Sag in dem Fall, "
        "dass mehr drin ist, und achte besonders auf das Eiweiß. "
    ),
}

COACH_RULES = (
    "Schreibe auf Deutsch, duze die Person, bleib freundlich und konkret. "
    "Nenne echte Zahlen aus den Daten statt allgemeiner Ratschläge. Wenn Tage "
    "ohne Einträge dabei sind, weise darauf hin, dass sie die Auswertung "
    "verfälschen, statt sie als Null-Tage zu bewerten. Steht tagesbeginn_uhr "
    "über 0, beginnt ein Tag erst zu dieser Stunde – Essen davor gehört noch "
    "zum Vortag, behandle es also nicht als verspätet oder als eigenen Tag. "
    "Steht bei eiweiss_g "
    "null, wurde für diesen Tag kein Eiweiß erfasst – behandle das als "
    "unbekannt und nicht als null Gramm. Gib keine medizinischen "
    "Empfehlungen und keine Diagnosen."
)


def coach_system(direction: str) -> str:
    """Systemprompt für die Einschätzung, passend zur Zielrichtung."""
    return (
        "Du bist ein sachlicher Ernährungs-Coach in einem privaten "
        "Kalorien-Tagebuch. "
        + COACH_GOAL.get(direction, COACH_GOAL["gain"])
        + COACH_RULES
    )


def coach_analysis(data: dict, direction: str = "gain") -> dict:
    """Bewertet die letzten Tage gegenüber dem Kalorienziel."""
    prompt = (
        coach_system(direction)
        + "\n\nHier sind die Daten als JSON:\n"
        + json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)
    )
    # Niedrige Denkstufe auch hier: Die Einschätzung fasst 14 Tageswerte
    # zusammen, dafür reicht sie, und mit "medium" lief der Aufruf auf dem Free
    # Tier regelmäßig in den Proxy-Timeout.
    result = _json_call(prompt, COACH_SCHEMA, max_tokens=16000, thinking="low")
    tips = [str(t).strip() for t in (result.get("tips") or []) if str(t).strip()]
    return {
        "status": result.get("status") or "no_data",
        "headline": (result.get("headline") or "").strip()[:120],
        "message": (result.get("message") or "").strip()[:1200],
        "tips": tips[:3],
    }
