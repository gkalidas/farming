import base64
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from core import inference, registry
from db.setup import init as db_init
from modules.classifier import ClassifierModule
from modules.photo import PhotoModule
from modules.soil import SoilModule
from modules.weather import WeatherModule

# ── bootstrap ─────────────────────────────────────────────────────────────────
db_init()

upload_dir = Path(config.UPLOAD_DIR)
upload_dir.mkdir(exist_ok=True)
Path(config.MODELS_DIR).mkdir(exist_ok=True)

photo_mod      = PhotoModule()
classifier_mod = ClassifierModule(model_dir=config.MODELS_DIR)

registry.register(WeatherModule())
registry.register(SoilModule())

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Khetai")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/analyse")
async def analyse(
    crop:     str        = Form(...),
    location: str        = Form(""),
    image:    UploadFile = File(...),
):
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(400, "Empty image upload")

    ts       = datetime.now(timezone.utc)
    img_path = Path(config.UPLOAD_DIR) / f"{ts.strftime('%Y%m%d_%H%M%S')}_{image.filename}"
    img_path.write_bytes(img_bytes)
    today    = ts.date().isoformat()

    # ── run disease detection ─────────────────────────────────────────────
    # prefer the fast ONNX classifier; fall back to vision LLM if no model yet
    classifier_ctx = await classifier_mod.classify(img_bytes, crop)
    if classifier_ctx.available:
        photo_ctx = classifier_ctx
    else:
        img_b64   = base64.b64encode(img_bytes).decode()
        photo_ctx = await photo_mod.analyze(img_b64, crop)

    # ── run all parameter modules ─────────────────────────────────────────
    param_ctxs = []
    for mod in registry.all_modules():
        ctx = await mod.get_context(crop=crop, location=location, date=today)
        param_ctxs.append(ctx)

    all_ctxs = [photo_ctx] + param_ctxs

    # ── inference (text LLM synthesises everything) ───────────────────────
    result = await inference.run(crop=crop, contexts=all_ctxs)

    # ── persist ───────────────────────────────────────────────────────────
    modules_summary = [
        {"module": c.module_name, "available": c.available, "summary": c.summary}
        for c in all_ctxs
    ]
    con = sqlite3.connect(config.DB_PATH)
    con.execute(
        """INSERT INTO analyses
           (created_at, crop, location, image_path, visual_diag, result_json, modules_json)
           VALUES (?,?,?,?,?,?,?)""",
        (
            ts.isoformat(), crop, location, str(img_path),
            photo_ctx.detail.get("raw_diagnosis", photo_ctx.summary),
            json.dumps(result),
            json.dumps(modules_summary),
        ),
    )
    con.commit()
    con.close()

    return JSONResponse({
        "result":           result,
        "visual_diagnosis": photo_ctx.detail.get("raw_diagnosis", photo_ctx.summary),
        "modules":          modules_summary,
    })


@app.get("/api/history")
async def history():
    con = sqlite3.connect(config.DB_PATH)
    rows = con.execute(
        "SELECT id, created_at, crop, location, result_json FROM analyses ORDER BY id DESC LIMIT 30"
    ).fetchall()
    con.close()
    return [
        {"id": r[0], "created_at": r[1], "crop": r[2], "location": r[3], "result": json.loads(r[4])}
        for r in rows
    ]


@app.get("/api/status")
async def status():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r      = await c.get(f"{config.OLLAMA_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        models = []

    classifier_models = [p.stem for p in Path(config.MODELS_DIR).glob("*.onnx")]

    return {
        "ollama":             bool(models),
        "ollama_models":      models,
        "vision_model":       config.VISION_MODEL,
        "text_model":         config.TEXT_MODEL,
        "classifier_models":  classifier_models,
    }
