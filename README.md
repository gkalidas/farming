# Khetai 🌱 — Local Crop Advisor

Upload a photo of any crop → get a diagnosis, immediate actions, and contextual advice powered by a local vision model. No cloud, no API costs, no connectivity required.

## How it works

```
Photo + Crop + Location
        │
  ┌─────▼──────┐
  │ Photo      │  llama3.2-vision  →  visual diagnosis
  │ Module     │
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Weather    │  OpenWeatherMap (cached, offline fallback)
  │ Module     │
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Inference  │  llama3 (text)  →  structured action plan
  │ Engine     │
  └─────┬──────┘
        │
  Diagnosis  ·  Severity  ·  Actions  ·  Timeline
```

Adding a new parameter (soil, water, market prices) = one new file in `modules/`.

## Setup on Linux (Ubuntu 22/24)

### 1. Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull the models
```bash
# Vision model — 8 GB download, needs 12 GB RAM
ollama pull llama3.2-vision:11b

# Text inference model — 4.7 GB (use the one you already have)
ollama pull llama3:latest
```

> **Lower-RAM option:** replace `llama3.2-vision:11b` with `llava:7b` (4.7 GB, needs 8 GB RAM).  
> Set `VISION_MODEL=llava:7b` in your `.env`.

### 3. Clone and install
```bash
git clone https://github.com/gkalidas/farming.git
cd farming
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure (optional)
```bash
cp .env.example .env
# Edit .env — add OPENWEATHER_KEY for live weather, leave blank for offline
```

### 5. Run
```bash
uvicorn main:app --host 0.0.0.0 --port 5002
# Open http://localhost:5002 — or use your laptop's IP on mobile
```

## Supported crops (Phase 1)
- Pomegranate
- Tomato
- Grape
- Onion
- Cotton

## Adding a new parameter module

Create `modules/soil.py`:
```python
from modules.base import BaseModule, ModuleContext

class SoilModule(BaseModule):
    name = "soil"

    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        # fetch or read soil data
        return ModuleContext(
            module_name=self.name,
            available=True,
            summary="Soil pH 6.2, nitrogen low, potassium adequate",
            detail={"ph": 6.2, "nitrogen": "low"},
        )
```

Register it in `main.py`:
```python
from modules.soil import SoilModule
registry.register(SoilModule())
```

That's it. The inference engine picks it up automatically.

## Stack

```
Backend:   FastAPI + SQLite (WAL)
Frontend:  Vanilla JS, mobile-first, no build step
Models:    Ollama — llama3.2-vision (vision) + llama3 (inference)
```
