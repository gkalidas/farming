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
        kb = json.loads(path.read_text())
        diseases = kb.get("diseases", {})
        lines = [f"KNOWLEDGE BASE for {crop} ({kb.get('primary_region','')}, variety: {kb.get('dominant_variety','unknown')}):"]
        for disease, info in diseases.items():
            lines.append(f"\n  {disease}:")
            lines.append(f"    Symptoms: {info.get('visual_symptoms','')}")
            lines.append(f"    Favourable conditions: {info.get('favourable_conditions','')}")
            if info.get("severity_note"):
                lines.append(f"    Severity note: {info['severity_note']}")
        return "\n".join(lines)
    except Exception:
        return ""

_PROMPT = """\
You are an expert agricultural advisor specialising in {crop} cultivation in Maharashtra, India (Solapur/Nashik belt).
A farmer has uploaded a photo of their {crop} crop.

Below is what each analysis module found:

{context_block}

{kb_block}

Based on ALL the above information, provide a precise, actionable advisory tailored to current conditions.
Cross-reference the visual diagnosis with the knowledge base — if weather or soil conditions make a particular \
disease more likely, factor that in.

Respond ONLY with valid JSON — no markdown, no explanation, just the JSON object:
{{
  "condition":         "disease or condition name (e.g. 'Bacterial Blight' or 'Healthy')",
  "severity":          "healthy | mild | moderate | severe",
  "confidence":        "high | medium | low",
  "immediate_actions": ["step 1 with specific product/dosage", "step 2"],
  "do_not":            ["specific thing to avoid and why"],
  "watch_for":         ["specific symptom to monitor in next 7 days"],
  "weather_note":      "how current temperature/humidity/rain affects this disease specifically",
  "soil_note":         "how current soil pH/nitrogen affects this — omit if soil data unavailable",
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
