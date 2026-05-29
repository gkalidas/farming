import os

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "llama3.2-vision:11b")
TEXT_MODEL   = os.getenv("TEXT_MODEL",   "llama3:latest")
DB_PATH      = os.getenv("FARMING_DB",   "farming.db")
UPLOAD_DIR   = os.getenv("UPLOAD_DIR",   "uploads")
MODELS_DIR   = os.getenv("MODELS_DIR",   "models")
PORT         = int(os.getenv("PORT",     "5002"))
