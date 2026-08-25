"""Claude-API-Aufrufe: Kalorienschätzung und Ziel-Einschätzung.

Beide Aufrufe nutzen Structured Outputs (`output_config.format`), damit die
Antwort garantiert gültiges JSON nach unserem Schema ist – kein Parsen von
Freitext, kein Aufräumen von Markdown-Codeblöcken.
"""

import json
import logging
import os

import anthropic

log = logging.getLogger("kalorien.ai")

# Haiku als Standard: für Kalorienschätzungen reicht es und es ist das
# günstigste Modell. Über ANTHROPIC_MODEL umstellbar, z. B. auf claude-sonnet-5
# oder claude-opus-5, wenn die Schätzungen besser werden sollen.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()

# Der effort-Parameter existiert nicht auf jedem Modell – Haiku 4.5, Sonnet 4.5
# und die 3er-Reihe lehnen ihn mit HTTP 400 ab. Er wird deshalb nur gesendet,
# wenn das gewählte Modell ihn unterstützt.
_EFFORT_UNSUPPORTED = ("claude-haiku", "claude-sonnet-4-5", "claude-3")
SEND_EFFORT = (
    os.environ.get("AI_EFFORT", "").strip().lower() != "off"
    and not ANTHROPIC_MODEL.startswith(_EFFORT_UNSUPPORTED)
)

# Zeitbudget so wählen, dass ein Request inklusive Wiederholung deutlich unter
# dem 100-Sekunden-Timeout eines Cloudflare-Tunnels bleibt.
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 1

_client: anthropic.Anthropic | None = None


class AIError(Exception):
    """Fehler, dessen Text der Nutzerin gezeigt werden darf."""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            raise AIError("ANTHROPIC_API_KEY ist nicht gesetzt.")
        _client = anthropic.Anthropic(
            timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES
        )
    return _client


def _json_call(prompt: str, schema: dict, effort: str, max_tokens: int) -> dict:
    client = _get_client()
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if SEND_EFFORT:
        output_config["effort"] = effort
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise AIError("Der Anthropic-API-Key wird nicht akzeptiert.") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Anthropic-Limit erreicht. Bitte gleich nochmal versuchen.") from exc
    except anthropic.BadRequestError as exc:
        log.error("Anthropic lehnt die Anfrage ab (Modell %s): %s", ANTHROPIC_MODEL, exc.message)
        raise AIError(
            f"Die Anfrage wurde abgelehnt. Passt ANTHROPIC_MODEL ({ANTHROPIC_MODEL})?"
        ) from exc
    except anthropic.APIStatusError as exc:
        log.error("Anthropic-Fehler %s: %s", exc.status_code, exc.message)
        raise AIError("Die KI-Anfrage ist fehlgeschlagen.") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Keine Verbindung zur Anthropic-API.") from exc
    except Exception as exc:  # SDK-Änderungen o. Ä. dürfen keine 500-Seite erzeugen
        log.exception("Unerwarteter Fehler beim Anthropic-Aufruf")
        raise AIError("Die KI-Anfrage ist fehlgeschlagen.") from exc

    # stop_reason muss vor dem Zugriff auf content geprüft werden: bei einer
    # Ablehnung ist content leer oder unvollständig.
    if response.stop_reason == "refusal":
        raise AIError("Die KI hat diese Anfrage abgelehnt.")
    if response.stop_reason == "max_tokens":
        # Auf Modellen mit aktivem Thinking teilen sich Denk- und Antworttokens
        # das max_tokens-Budget; hier wurde es ausgeschöpft.
        log.error(
            "max_tokens (%d) erschöpft – Budget in ai.py erhöhen oder effort senken",
            max_tokens,
        )
        raise AIError("Die Antwort wurde abgeschnitten. Bitte nochmal versuchen.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
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
    "oder seine Einzelteile, nicht beides. Bei Unsicherheit schätze eher "
    "knapp als groß – eine zu hohe Schätzung lässt ein Tagesziel als erreicht "
    "erscheinen, obwohl es das nicht ist.\n\nAngabe: "
)


def estimate_meal(description: str) -> dict:
    """Schätzt kcal und Eiweiß für eine Freitext-Angabe."""
    result = _json_call(
        MEAL_PROMPT + description,
        MEAL_SCHEMA,
        effort="low",
        # Großzügig, weil Denk- und Antworttokens sich das Budget teilen.
        max_tokens=8192,
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
            "description": "Kurzbewertung der letzten Tage gegenüber dem Ziel.",
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

COACH_SYSTEM = (
    "Du bist ein sachlicher Ernährungs-Coach in einem privaten Kalorien-Tagebuch. "
    "Das Ziel der Person ist ZUZUNEHMEN: sie muss ihr Tagesziel erreichen oder "
    "leicht überschreiten, zu wenig ist das Problem, nicht zu viel. "
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


def coach_analysis(data: dict) -> dict:
    """Bewertet die letzten Tage gegenüber dem Kalorienziel."""
    prompt = (
        COACH_SYSTEM
        + "\n\nHier sind die Daten als JSON:\n"
        + json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)
    )
    result = _json_call(prompt, COACH_SCHEMA, effort="medium", max_tokens=16000)
    tips = [str(t).strip() for t in (result.get("tips") or []) if str(t).strip()]
    return {
        "status": result.get("status") or "no_data",
        "headline": (result.get("headline") or "").strip()[:120],
        "message": (result.get("message") or "").strip()[:1200],
        "tips": tips[:3],
    }
