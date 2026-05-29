import base64
import json
import sqlite3
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from core import inference, registry
from core.exif import extract as exif_extract
from core.geocode import resolve as geocode_resolve
from db.setup import init as db_init
from modules.classifier import ClassifierModule
from modules.crop_history import CropHistoryModule
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
app = FastAPI(title="Farming")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/plots")
async def create_plot(
    crop:       str        = Form(...),
    location:   str        = Form(...),
    notes:      str        = Form(""),
    image:      UploadFile = File(None),
):
    """Register a new crop plot. Optionally attach a planting photo to auto-extract datetime."""
    planted_at = date.today().isoformat()
    lat = lon = None

    if image:
        img_bytes  = await image.read()
        meta       = exif_extract(img_bytes)
        if meta.taken_at:
            planted_at = meta.taken_at.date().isoformat()
        if meta.lat and meta.lon:
            lat, lon = meta.lat, meta.lon

    # geocode if we don't have GPS yet
    if not lat or not lon:
        coords = await geocode_resolve(location)
        if coords:
            lat, lon, _ = coords

    ts  = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(config.DB_PATH)
    cur = con.execute(
        "INSERT INTO crop_plots (created_at, crop, location, planted_at, lat, lon, notes) VALUES (?,?,?,?,?,?,?)",
        (ts, crop, location, planted_at, lat, lon, notes),
    )
    plot_id = cur.lastrowid
    con.commit()
    con.close()

    return JSONResponse({
        "plot_id":    plot_id,
        "crop":       crop,
        "location":   location,
        "planted_at": planted_at,
        "lat":        lat,
        "lon":        lon,
    })


@app.get("/api/plots")
async def list_plots():
    con  = sqlite3.connect(config.DB_PATH)
    rows = con.execute(
        "SELECT id, crop, location, planted_at, notes FROM crop_plots ORDER BY id DESC"
    ).fetchall()
    con.close()
    return [
        {"id": r[0], "crop": r[1], "location": r[2], "planted_at": r[3], "notes": r[4]}
        for r in rows
    ]


@app.post("/api/analyse")
async def analyse(
    crop:     str        = Form(...),
    location: str        = Form(""),
    plot_id:  Optional[int] = Form(None),
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

    # crop lifecycle history (only if a plot is linked)
    if plot_id:
        history_ctx = await CropHistoryModule(plot_id=plot_id).get_context(
            crop=crop, location=location, date_str=today
        )
        param_ctxs.append(history_ctx)

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
