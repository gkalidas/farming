import io
from pathlib import Path

import numpy as np

from .base import BaseModule, ModuleContext

# Labels match the Kaggle pomegranate dataset (5 classes)
# Update this dict when you fine-tune on a new crop
# Maps crop → ordered list of class names (must match ImageFolder sorted order = alphabetical)
# Folder names in dataset → display names used here
#   Alternaria        → Alternaria Fruit Spot
#   Anthracnose       → Anthracnose
#   Bacterial_Blight  → Bacterial Blight
#   Cercospora        → Cercospora Fruit Spot
#   Healthy           → Healthy
CROP_LABELS: dict[str, list[str]] = {
    "pomegranate": [
        "Alternaria Fruit Spot",   # alphabetical: Alternaria < Anthracnose
        "Anthracnose",
        "Bacterial Blight",
        "Cercospora Fruit Spot",
        "Healthy",
    ],
}

# ImageNet normalisation (matches the MobileNetV2 training)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class ClassifierModule(BaseModule):
    """
    Runs a fine-tuned ONNX model (MobileNetV2 head) to classify crop disease.
    Falls back gracefully if the model file doesn't exist yet.
    """
    name = "classifier"

    def __init__(self, model_dir: str = "models"):
        self._model_dir  = Path(model_dir)
        self._sessions:  dict[str, object] = {}   # crop → ort.InferenceSession

    def _load(self, crop: str):
        """Lazy-load the ONNX session for a crop."""
        if crop in self._sessions:
            return self._sessions[crop]

        model_path = self._model_dir / f"{crop}.onnx"
        if not model_path.exists():
            return None

        try:
            import onnxruntime as ort
            session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            self._sessions[crop] = session
            return session
        except Exception:
            return None

    def _preprocess(self, image_bytes: bytes) -> np.ndarray:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - _MEAN) / _STD
        return arr.transpose(2, 0, 1)[np.newaxis]   # (1, 3, 224, 224)

    async def classify(self, image_bytes: bytes, crop: str) -> ModuleContext:
        session = self._load(crop)
        if session is None:
            return ModuleContext(
                module_name=self.name,
                available=False,
                summary=f"Classifier: no trained model for '{crop}' yet — run train/fine_tune.py",
                detail={"model_missing": True},
            )

        try:
            arr     = self._preprocess(image_bytes)
            inp     = session.get_inputs()[0].name
            logits  = session.run(None, {inp: arr})[0][0]
            probs   = _softmax(logits)
            top_idx = int(probs.argmax())
            labels  = CROP_LABELS.get(crop, [f"Class {i}" for i in range(len(probs))])
            label   = labels[top_idx] if top_idx < len(labels) else f"Class {top_idx}"
            conf    = float(probs[top_idx])

            top3 = sorted(
                [(labels[i] if i < len(labels) else f"Class {i}", float(probs[i]))
                 for i in range(len(probs))],
                key=lambda x: -x[1],
            )[:3]

            return ModuleContext(
                module_name=self.name,
                available=True,
                summary=f"Classifier: {label} ({conf:.0%} confidence)",
                detail={
                    "condition":   label,
                    "confidence":  conf,
                    "top3":        top3,
                },
            )
        except Exception as e:
            return ModuleContext(
                module_name=self.name, available=False,
                summary=f"Classifier error: {e}",
            )

    # satisfies abstract contract; real entry point is classify()
    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        return ModuleContext(
            module_name=self.name, available=False,
            summary="Classifier: no image provided",
        )
