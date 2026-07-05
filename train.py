import os
from pathlib import Path
from typing import List, Tuple, Dict

import librosa
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "training_checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "model_checkpoint.pt"
CAP_SECONDS = 7200.0
TARGET_SR = 16000
BATCH_SIZE = 4
EPOCHS = 10
LEARNING_RATE = 2e-4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

SCAM_TEXTS = [
    "urgent emergency bank account locked",
    "send money immediately to secure your funds",
    "verify your bank account and password now",
    "collision accident hospital charge payment",
    "reward payment credit card fee",
    "డబ్బులు పంపండి బ్యాంక్ ఖాతా підтвердити",
]
SAFE_TEXTS = [
    "meeting schedule update for project review",
    "friendly voice note about the weekend plans",
    "confirming appointment time and agenda",
    "pleasant conversation about weather and travel",
    "routine check in with family and friends",
]

VOCAB = {
    "urgent": 0,
    "emergency": 1,
    "bank": 2,
    "account": 3,
    "locked": 4,
    "money": 5,
    "password": 6,
    "payment": 7,
    "credit": 8,
    "card": 9,
    "fee": 10,
    "verify": 11,
    "hospital": 12,
    "accident": 13,
    "reward": 14,
    "send": 15,
    "help": 16,
    "డబ్బులు": 17,
    "transfer": 18,
    "secure": 19,
}
VOCAB_SIZE = len(VOCAB)


def scan_dataset(root: Path, cap_seconds: float) -> List[Tuple[Path, float, bool, int, str]]:
    selected: List[Tuple[Path, float, bool, int, str]] = []
    for group_name, label in [("real", 0), ("fake", 1)]:
        folder = root / group_name
        if not folder.exists():
            continue

        cumulative = 0.0
        for file_path in sorted(folder.rglob("*.wav")):
            duration = float(librosa.get_duration(filename=str(file_path)))
            if duration <= 0.0:
                continue
            if cumulative >= cap_seconds:
                break

            if duration + cumulative > cap_seconds:
                usable = cap_seconds - cumulative
                partial = True
            else:
                usable = duration
                partial = False

            transcript = build_placeholder_transcript(label, partial)
            semantic_label = 1 if any(term in transcript for term in ["urgent", "bank", "డబ్బులు", "payment", "verify"]) else 0
            selected.append((file_path, usable, partial, label, transcript))
            cumulative += usable
            if cumulative >= cap_seconds:
                break

        print(f"Loaded {len([item for item in selected if item[3] == label])} {group_name} files totaling {cumulative / 3600:.3f} hours")

    total_hours = sum(entry[1] for entry in selected) / 3600.0
    print(f"Total selected hours across classes: {total_hours:.3f}h")
    return selected


def build_placeholder_transcript(label: int, partial: bool) -> str:
    if label == 1:
        return SCAM_TEXTS[np.random.randint(0, len(SCAM_TEXTS))]
    if np.random.rand() < 0.2:
        return SCAM_TEXTS[np.random.randint(0, len(SCAM_TEXTS))]
    return SAFE_TEXTS[np.random.randint(0, len(SAFE_TEXTS))]


def text_to_vector(text: str) -> torch.Tensor:
    vector = np.zeros(VOCAB_SIZE, dtype=np.float32)
    for token in text.lower().split():
        if token in VOCAB:
            vector[VOCAB[token]] += 1.0
    return torch.tensor(vector, dtype=torch.float32)


def extract_acoustic_features(path: Path, duration: float, partial: bool) -> torch.Tensor:
    load_kwargs = {"sr": TARGET_SR, "mono": True}
    if partial:
        load_kwargs["duration"] = float(duration)
    y, sr = librosa.load(str(path), **load_kwargs)
    hop_length = int(0.020 * sr)
    n_fft = int(0.040 * sr)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=n_fft, hop_length=hop_length)
    delta = librosa.feature.delta(mfcc)
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    f0_values = f0[~np.isnan(f0)]
    f0_var = float(np.var(f0_values)) if f0_values.size else 0.0

    features = [
        np.mean(mfcc, axis=1),
        np.std(mfcc, axis=1),
        np.mean(delta, axis=1),
        np.std(delta, axis=1),
        np.array([f0_var, float(np.mean(np.abs(y)))]),
    ]
    feature_vector = np.concatenate([arr.flatten() for arr in features], axis=0).astype(np.float32)
    return torch.tensor(feature_vector, dtype=torch.float32)


class NeuroSyncDataset(Dataset):
    def __init__(self, entries: List[Tuple[Path, float, bool, int, str]]):
        self.entries = entries

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        file_path, duration, partial, acoustic_label, transcript = self.entries[idx]
        acoustic_features = extract_acoustic_features(file_path, duration, partial)
        semantic_vector = text_to_vector(transcript)
        semantic_label = 1 if any(keyword in transcript for keyword in ["urgent", "bank", "డబ్బులు", "payment", "verify"]) else 0
        return {
            "acoustic_features": acoustic_features,
            "semantic_features": semantic_vector,
            "acoustic_label": torch.tensor(acoustic_label, dtype=torch.long),
            "semantic_label": torch.tensor(semantic_label, dtype=torch.long),
        }


class DualHeadClassifier(nn.Module):
    def __init__(self, acoustic_dim: int, semantic_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.acoustic_branch = nn.Sequential(
            nn.Linear(acoustic_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
        )
        self.semantic_branch = nn.Sequential(
            nn.Linear(semantic_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
        )
        self.shared = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
        )
        self.head_acoustic = nn.Linear(hidden_dim, 2)
        self.head_semantic = nn.Linear(hidden_dim, 2)

    def forward(self, acoustic_input: torch.Tensor, semantic_input: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        acoustic_hidden = self.acoustic_branch(acoustic_input)
        semantic_hidden = self.semantic_branch(semantic_input)
        combined = torch.cat([acoustic_hidden, semantic_hidden], dim=1)
        fused = self.shared(combined)
        return self.head_acoustic(fused), self.head_semantic(fused)


def load_checkpoint(model: nn.Module, optimizer: torch.optim.Optimizer) -> int:
    if not CHECKPOINT_PATH.exists():
        return 0
    checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    start_epoch = checkpoint.get("epoch", 0) + 1
    print("🔄 Found existing training state tracker. Continuing model training from the last saved epoch/step index...")
    return start_epoch


def save_checkpoint(model: nn.Module, optimizer: torch.optim.Optimizer, epoch: int) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        CHECKPOINT_PATH,
    )
    print(f"💾 Checkpoint saved at epoch {epoch} to {CHECKPOINT_PATH}")


def collate_batch(batch: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
    return {
        "acoustic_features": torch.stack([item["acoustic_features"] for item in batch]),
        "semantic_features": torch.stack([item["semantic_features"] for item in batch]),
        "acoustic_label": torch.stack([item["acoustic_label"] for item in batch]),
        "semantic_label": torch.stack([item["semantic_label"] for item in batch]),
    }


def train() -> None:
    entries = scan_dataset(DATASET_ROOT, CAP_SECONDS)
    if not entries:
        raise RuntimeError(f"No dataset entries found in {DATASET_ROOT}")

    total_hours_loaded = sum(item[1] for item in entries) / 3600.0
    print(f"✅ Total Hours Loaded: {total_hours_loaded:.3f} hours")

    dataset = NeuroSyncDataset(entries)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch)

    sample = dataset[0]
    acoustic_dim = sample["acoustic_features"].shape[0]
    semantic_dim = sample["semantic_features"].shape[0]

    model = DualHeadClassifier(acoustic_dim=acoustic_dim, semantic_dim=semantic_dim)
    model.to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    start_epoch = load_checkpoint(model, optimizer)
    if start_epoch == 0:
        print("⚙️ Starting from base model weights.")

    for epoch in range(start_epoch, EPOCHS):
        model.train()
        running_loss = 0.0
        correct_acoustic = 0
        correct_semantic = 0
        total_samples = 0

        for batch_idx, batch in enumerate(dataloader, start=1):
            acoustic_inputs = batch["acoustic_features"].to(DEVICE)
            semantic_inputs = batch["semantic_features"].to(DEVICE)
            acoustic_labels = batch["acoustic_label"].to(DEVICE)
            semantic_labels = batch["semantic_label"].to(DEVICE)

            logits_acoustic, logits_semantic = model(acoustic_inputs, semantic_inputs)
            loss_acoustic = criterion(logits_acoustic, acoustic_labels)
            loss_semantic = criterion(logits_semantic, semantic_labels)
            loss = loss_acoustic + loss_semantic

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * acoustic_inputs.size(0)
            total_samples += acoustic_inputs.size(0)

            correct_acoustic += (logits_acoustic.argmax(dim=1) == acoustic_labels).sum().item()
            correct_semantic += (logits_semantic.argmax(dim=1) == semantic_labels).sum().item()

            if batch_idx % 5 == 0 or batch_idx == len(dataloader):
                print(
                    f"Epoch {epoch + 1}/{EPOCHS} | Batch {batch_idx}/{len(dataloader)} | "
                    f"Loss: {loss.item():.4f}"
                )

        epoch_loss = running_loss / max(1, total_samples)
        acoustic_acc = correct_acoustic / max(1, total_samples)
        semantic_acc = correct_semantic / max(1, total_samples)

        print(
            f"🔔 Epoch {epoch + 1} complete | Loss: {epoch_loss:.4f} | "
            f"Acoustic Acc: {acoustic_acc:.3f} | Semantic Acc: {semantic_acc:.3f}"
        )

        save_checkpoint(model, optimizer, epoch)

    print("🏁 Training finished. Final checkpoint written.")


if __name__ == "__main__":
    train()
