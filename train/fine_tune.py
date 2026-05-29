"""
Fine-tune MobileNetV2 on a crop disease dataset and export to ONNX.

Usage:
  python train/fine_tune.py \
    --data "data/pomegranate/Pomegranate Fruit Diseases Dataset for Deep Learning Models/Pomegranate Diseases Dataset/Pomegranate Diseases Dataset" \
    --crop pomegranate

Dataset layout (ImageFolder format — one subfolder per class):
  <data_dir>/
    Alternaria/
    Anthracnose/
    Bacterial_Blight/
    Cercospora/
    Healthy/
"""

import argparse
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, models, transforms

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── labels: must match classifier.py CROP_LABELS (alphabetical folder order) ─
LABELS: dict[str, list[str]] = {
    "pomegranate": [
        "Alternaria Fruit Spot",   # Alternaria
        "Anthracnose",             # Anthracnose
        "Bacterial Blight",        # Bacterial_Blight
        "Cercospora Fruit Spot",   # Cercospora
        "Fruit Borer",             # Ectomyelois
        "Healthy",                 # Healthy
        "Sunburn",                 # Sunburn
    ],
}

TF_TRAIN = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.RandomCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=.3, contrast=.3, saturation=.2),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

TF_VAL = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


# Module-level class — required for multiprocessing pickle compatibility
class SplitDataset(Dataset):
    def __init__(self, img_paths: list, labels: list, transform):
        self.img_paths = img_paths
        self.labels    = labels
        self.transform = transform

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, i):
        img = Image.open(self.img_paths[i]).convert("RGB")
        return self.transform(img), self.labels[i]


def train(data_dir: Path, crop: str, epochs: int, batch: int, lr: float, out_dir: Path):
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")

    # ── build split datasets ──────────────────────────────────────────────────
    full_ds = datasets.ImageFolder(str(data_dir))
    all_idx = list(range(len(full_ds)))
    all_lbl = full_ds.targets
    tr_idx, va_idx = train_test_split(all_idx, test_size=0.2, stratify=all_lbl, random_state=42)

    def make_ds(indices, tf):
        paths  = [full_ds.imgs[i][0] for i in indices]
        labels = [full_ds.imgs[i][1] for i in indices]
        return SplitDataset(paths, labels, tf)

    tr_ds = make_ds(tr_idx, TF_TRAIN)
    va_ds = make_ds(va_idx, TF_VAL)

    # pin_memory not supported on MPS
    pin = device.type == "cuda"
    nw  = 0 if device.type == "mps" else 2   # MPS + multiprocessing is unreliable

    tr_loader = DataLoader(tr_ds, batch_size=batch, shuffle=True,  num_workers=nw, pin_memory=pin)
    va_loader = DataLoader(va_ds, batch_size=batch, shuffle=False, num_workers=nw, pin_memory=pin)

    num_classes = len(LABELS[crop])
    print(f"Classes: {num_classes} | Train: {len(tr_ds)} | Val: {len(va_ds)}")
    print(f"Folder → class mapping: {full_ds.class_to_idx}")

    # ── model ─────────────────────────────────────────────────────────────────
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    model = model.to(device)

    # freeze backbone for first 2 epochs
    for p in model.features.parameters():
        p.requires_grad = False

    criterion = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.classifier.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=lr, epochs=2, steps_per_epoch=len(tr_loader)
    )

    best_acc  = 0.0
    best_path = out_dir / f"{crop}_best.pt"

    for epoch in range(epochs):
        # unfreeze backbone at epoch 2, lower lr
        if epoch == 2:
            for p in model.features.parameters():
                p.requires_grad = True
            opt = torch.optim.Adam(model.parameters(), lr=lr / 10)

        # ── train ─────────────────────────────────────────────────────────────
        model.train()
        tr_loss = tr_correct = tr_total = 0
        t0 = time.time()
        for imgs, lbls in tr_loader:
            imgs, lbls = imgs.to(device), lbls.to(device)
            opt.zero_grad()
            out  = model(imgs)
            loss = criterion(out, lbls)
            loss.backward()
            opt.step()
            if epoch < 2:
                scheduler.step()
            tr_loss    += loss.item() * len(imgs)
            tr_correct += (out.argmax(1) == lbls).sum().item()
            tr_total   += len(imgs)

        # ── validate ──────────────────────────────────────────────────────────
        model.eval()
        va_correct = va_total = 0
        with torch.no_grad():
            for imgs, lbls in va_loader:
                imgs, lbls = imgs.to(device), lbls.to(device)
                out = model(imgs)
                va_correct += (out.argmax(1) == lbls).sum().item()
                va_total   += len(imgs)

        va_acc = va_correct / va_total
        print(
            f"Epoch {epoch+1:02d}/{epochs} | "
            f"loss {tr_loss/tr_total:.4f} | "
            f"train {tr_correct/tr_total:.3f} | "
            f"val {va_acc:.3f} | "
            f"{time.time()-t0:.0f}s"
        )
        if va_acc > best_acc:
            best_acc = va_acc
            torch.save(model.state_dict(), best_path)
            print(f"           ✓ best saved (val={va_acc:.3f})")

    print(f"\nBest val accuracy: {best_acc:.3f}")

    # ── ONNX export ───────────────────────────────────────────────────────────
    model.load_state_dict(torch.load(best_path, map_location="cpu"))
    model_cpu = model.cpu().eval()
    dummy     = torch.randn(1, 3, 224, 224)
    onnx_path = out_dir / f"{crop}.onnx"

    torch.onnx.export(
        model_cpu, dummy, str(onnx_path),
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    print(f"ONNX model saved → {onnx_path}")
    print(f"Copy it to models/{crop}.onnx to activate the classifier.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data",   required=True)
    ap.add_argument("--crop",   default="pomegranate")
    ap.add_argument("--epochs", type=int,   default=10)
    ap.add_argument("--batch",  type=int,   default=32)
    ap.add_argument("--lr",     type=float, default=1e-3)
    ap.add_argument("--out",    default="models")
    args = ap.parse_args()

    if args.crop not in LABELS:
        sys.exit(f"Unknown crop '{args.crop}'. Add it to LABELS dict first.")

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    train(Path(args.data), args.crop, args.epochs, args.batch, args.lr, out_dir)
