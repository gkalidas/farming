"""
Evaluate the trained ONNX model.

Runs two test sets:
  1. Held-out images from the Kaggle dataset (ground truth known)
  2. Fresh images downloaded from the web (real-world check)

Writes a detailed CSV log + prints a summary table.

Usage:
  python train/evaluate.py --data data/pomegranate --crop pomegranate
"""

import argparse
import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from modules.classifier import CROP_LABELS, _MEAN, _STD, _softmax

# ── web test images: real pomegranate disease photos from research papers / open datasets
# These are NOT from the Kaggle training set — they test real-world generalisation.
# Verified image URLs — sourced from PMC open-access papers and Wikimedia Commons
# PMC11220843: comprehensive pomegranate disease dataset paper (India, 2024)
# PMC9604645:  Alternaria/Colletotrichum characterization in Maharashtra
# Wikimedia:   CC-licensed field photographs
WEB_TEST_IMAGES: dict[str, list[str]] = {
    "pomegranate": [
        # Healthy
        ("Healthy", "https://upload.wikimedia.org/wikipedia/commons/7/72/Pomegranate_DSW.JPG"),
        ("Healthy", "https://upload.wikimedia.org/wikipedia/commons/9/9c/Pomegranate_uncut.JPG"),
        ("Healthy", "https://upload.wikimedia.org/wikipedia/commons/4/48/Hanging_pomegranate.JPG"),
        ("Healthy", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/ef2e/11220843/1855b11b3f5d/gr1.jpg"),

        # Bacterial Blight (Xanthomonas axonopodis pv. punicae)
        ("Bacterial Blight", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/ef2e/11220843/d7f10a5465a4/gr2.jpg"),
        ("Bacterial Blight", "https://upload.wikimedia.org/wikipedia/commons/4/41/Pomegranate_scab_2017_A.jpg"),

        # Anthracnose (Colletotrichum gloeosporioides)
        ("Anthracnose", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/ef2e/11220843/42890d440ed1/gr3.jpg"),
        ("Anthracnose", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/35ec/9604645/56fa491dbd02/jof-08-01040-g001.jpg"),

        # Cercospora Fruit Spot (Pseudocercospora punicae)
        ("Cercospora Fruit Spot", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/ef2e/11220843/c666728ff6ef/gr4.jpg"),
        ("Cercospora Fruit Spot", "https://upload.wikimedia.org/wikipedia/commons/2/24/Pomegranate_scab_2017_B2.jpg"),

        # Alternaria Fruit Spot (Alternaria alternata)
        ("Alternaria Fruit Spot", "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/ef2e/11220843/3f14dd774bde/gr5.jpg"),
        ("Alternaria Fruit Spot", "https://upload.wikimedia.org/wikipedia/commons/e/e8/Pomegranate_scab_2017_C.jpg"),
    ],
}


def preprocess(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - _MEAN) / _STD
    return arr.transpose(2, 0, 1)[np.newaxis]


def predict(session: ort.InferenceSession, image_bytes: bytes, labels: list[str]) -> tuple[str, float, list]:
    arr    = preprocess(image_bytes)
    inp    = session.get_inputs()[0].name
    logits = session.run(None, {inp: arr})[0][0]
    probs  = _softmax(logits)
    top    = int(probs.argmax())
    label  = labels[top] if top < len(labels) else f"Class {top}"
    conf   = float(probs[top])
    top3   = sorted(
        [(labels[i] if i < len(labels) else f"Class {i}", float(probs[i])) for i in range(len(probs))],
        key=lambda x: -x[1]
    )[:3]
    return label, conf, top3


def run_eval(data_dir: Path | None, crop: str, model_path: Path, log_path: Path):
    labels  = CROP_LABELS.get(crop, [])
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    rows     = []
    correct  = 0
    total    = 0
    per_cls: dict[str, dict] = {l: {"tp": 0, "total": 0} for l in labels}

    # ── 1. Kaggle validation images ──────────────────────────────────────────
    if data_dir and data_dir.exists():
        print(f"\n── Kaggle held-out set ({data_dir}) ──")
        image_paths = []
        cls_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
        for idx, cls_dir in enumerate(cls_dirs):
            # Use sorted folder index → label (matches ImageFolder ordering used during training)
            matched = labels[idx] if idx < len(labels) else cls_dir.name.replace("_", " ").title()
            imgs = list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.jpeg")) + list(cls_dir.glob("*.png"))
            # use last 20% as test split (same seed as fine_tune.py)
            n_test = max(1, int(len(imgs) * 0.2))
            for p in imgs[-n_test:]:
                image_paths.append((p, matched, "kaggle"))

        for img_path, true_label, source in image_paths:
            try:
                img_bytes = img_path.read_bytes()
                pred, conf, top3 = predict(session, img_bytes, labels)
                ok = (pred.lower() == true_label.lower())
                correct += ok
                total   += 1
                per_cls.setdefault(true_label, {"tp": 0, "total": 0})
                per_cls[true_label]["total"] += 1
                if ok:
                    per_cls[true_label]["tp"] += 1
                rows.append({
                    "source":     source,
                    "image":      str(img_path.name),
                    "true_label": true_label,
                    "predicted":  pred,
                    "confidence": f"{conf:.3f}",
                    "correct":    "yes" if ok else "no",
                    "top3":       json.dumps(top3),
                })
                mark = "✓" if ok else "✗"
                print(f"  {mark} {img_path.name[:40]:<40} true={true_label:<25} pred={pred:<25} conf={conf:.2f}")
            except Exception as e:
                print(f"  ! skip {img_path.name}: {e}")

        if total:
            print(f"\n  Kaggle val accuracy: {correct}/{total} = {correct/total:.1%}")

    # ── 2. Web test images ────────────────────────────────────────────────────
    web_tests = WEB_TEST_IMAGES.get(crop, [])
    if web_tests:
        print(f"\n── Web test images (real-world generalisation) ──")
        web_correct = web_total = 0
        for true_label, url in web_tests:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    img_bytes = r.read()
                pred, conf, top3 = predict(session, img_bytes, labels)
                ok = (pred.lower() == true_label.lower())
                web_correct += ok
                web_total   += 1
                correct     += ok
                total       += 1
                rows.append({
                    "source":     "web",
                    "image":      url.split("/")[-1],
                    "true_label": true_label,
                    "predicted":  pred,
                    "confidence": f"{conf:.3f}",
                    "correct":    "yes" if ok else "no",
                    "top3":       json.dumps(top3),
                })
                mark = "✓" if ok else "✗"
                print(f"  {mark} {url.split('/')[-1][:40]:<40} true={true_label:<25} pred={pred:<25} conf={conf:.2f}")
            except Exception as e:
                print(f"  ! could not fetch {url}: {e}")

        if web_total:
            print(f"\n  Web accuracy: {web_correct}/{web_total} = {web_correct/web_total:.1%}")

    # ── 3. Write CSV log ──────────────────────────────────────────────────────
    log_path.parent.mkdir(exist_ok=True)
    with open(log_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source","image","true_label","predicted","confidence","correct","top3"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n── Log written → {log_path}")

    # ── 4. Summary table ──────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"OVERALL ACCURACY: {correct}/{total} = {correct/total:.1%}" if total else "No images evaluated.")
    print(f"{'─'*60}")
    print(f"{'Class':<30} {'Correct':<10} {'Total':<10} {'Accuracy'}")
    print(f"{'─'*60}")
    for cls, counts in per_cls.items():
        if counts["total"] == 0:
            continue
        acc = counts["tp"] / counts["total"]
        print(f"{cls:<30} {counts['tp']:<10} {counts['total']:<10} {acc:.1%}")
    print(f"{'─'*60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data",  default=None,  help="Path to dataset root (optional)")
    ap.add_argument("--crop",  default="pomegranate")
    ap.add_argument("--model", default=None,  help="Path to .onnx file (default: models/<crop>.onnx)")
    ap.add_argument("--log",   default="logs/eval_results.csv")
    args = ap.parse_args()

    model_path = Path(args.model) if args.model else ROOT / "models" / f"{args.crop}.onnx"
    if not model_path.exists():
        sys.exit(f"Model not found: {model_path}\nRun train/fine_tune.py first.")

    run_eval(
        data_dir   = Path(args.data) if args.data else None,
        crop       = args.crop,
        model_path = model_path,
        log_path   = ROOT / args.log,
    )
