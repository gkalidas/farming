import json
from pathlib import Path

import httpx

from config import OLLAMA_URL, TEXT_MODEL
from modules.base import ModuleContext

_KB_DIR = Path(__file__).parent.parent / "crops"


def _load_kb(crop: str) -> str:
    path = _KB_DIR / f"{crop}.json"
    if not path.exists():
        return ""
    try:
        kb       = json.loads(path.read_text())
        diseases = kb.get("diseases", {})
        lines    = [
            f"KNOWLEDGE BASE for {crop}",
            f"Region: {kb.get('primary_region','')}",
            f"Dominant variety: {kb.get('dominant_variety','unknown')}",
        ]
        for disease, info in diseases.items():
            lines.append(f"\n--- {disease} ---")
            if info.get("causal_agent"):
                lines.append(f"  Cause: {info['causal_agent']}")
            lines.append(f"  Symptoms: {info.get('visual_symptoms','')}")
            if info.get("favourable_conditions"):
                lines.append(f"  Triggered by: {info['favourable_conditions']}")
            if info.get("severity_note"):
                lines.append(f"  Severity: {info['severity_note']}")
            if info.get("immediate_actions"):
                lines.append(f"  Immediate actions: {'; '.join(info['immediate_actions'])}")
            if info.get("preventive_measures"):
                lines.append(f"  Prevention: {'; '.join(info['preventive_measures'])}")
            if info.get("do_not"):
                lines.append(f"  Do NOT: {'; '.join(info['do_not'])}")
            if info.get("watch_for"):
                lines.append(f"  Watch for: {'; '.join(info['watch_for'])}")
            if info.get("timeline"):
                lines.append(f"  Timeline: {info['timeline']}")
        return "\n".join(lines)
    except Exception:
        return ""

_PROMPT = """\
You are an expert agricultural advisor specialising in {crop} cultivation in Maharashtra, India (Solapur/Nashik belt).
A farmer has uploaded a photo of their {crop} crop.

Below is what each analysis module found:

{context_block}

{kb_block}

Rules you MUST follow when building the advisory:

SPRAY TIMING:
- If rain is forecast or humidity > 85%, delay contact sprays (copper, mancozeb) — they wash off within 4h of rain.
- Never recommend spraying between 11am–3pm in temperatures above 35°C — phytotoxicity risk.
- If it rained heavily in the last 24h (>15mm), recommend waiting 48h before spraying unless systemic fungicide.

SOIL & MOISTURE:
- Sandy soil (sand% > 60): drains fast, disease spreads slower via water but drought stress cracks fruit — increase irrigation frequency, reduce volume.
- Clay soil (clay% > 40): retains moisture, creates high-humidity at canopy — fungal diseases spread faster, ensure drainage channels are clear.
- Estimate soil moisture from recent rainfall + soil type. Flag if root rot risk is high (clay + heavy rain + standing water).
- If no soil data is available, skip soil_note.

ROOT CONDITION:
- Cannot be determined from a photo alone. If disease pattern suggests root involvement (wilting despite irrigation, yellowing from base up), add a root inspection step to immediate_actions.

KNOWLEDGE BASE PRIORITY:
- Use the exact product names, dosages, and intervals from the knowledge base above.
- Do not invent products or dosages not present in the knowledge base.
- If the KB has no entry for the detected condition, say so clearly and recommend consulting a local KVK (Krishi Vigyan Kendra).

If the classifier flagged the condition as UNCERTAIN, reflect that uncertainty — do not give a confident diagnosis.

Respond ONLY with valid JSON — no markdown, no explanation, just the JSON object:
{{
  "condition":         "disease or condition name, or 'Unrecognised' if uncertain",
  "severity":          "healthy | mild | moderate | severe | unknown",
  "confidence":        "high | medium | low",
  "immediate_actions": ["step 1 with exact product/dosage from KB", "step 2"],
  "spray_timing":      "specific advice on when to spray given current weather conditions",
  "do_not":            ["specific thing to avoid and why"],
  "watch_for":         ["specific symptom to monitor in next 7 days"],
  "weather_note":      "how current + historical temperature/humidity/rain affects this disease",
  "soil_note":         "soil type drainage implications and estimated moisture risk — omit if no soil data",
  "root_note":         "root condition signals to check physically — omit if not relevant",
  "timeline":          "realistic timeline for improvement or escalation"
}}"""


async def run(crop: str, contexts: list[ModuleContext]) -> dict:
    context_block = "\n".join(
        f"[{c.module_name.upper()}] {c.summary}"
        for c in contexts
        if c.available
    )
    if not context_block:
        context_block = "No context modules available."

    kb_block = _load_kb(crop)

    payload = {
        "model": TEXT_MODEL,
        "prompt": _PROMPT.format(crop=crop, context_block=context_block, kb_block=kb_block),
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        r.raise_for_status()
        raw = r.json()["response"].strip()

    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {"error": "Model did not return valid JSON", "raw": raw}

    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}", "raw": raw}
