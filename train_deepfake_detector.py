import os
from pathlib import Path
from typing import List, Tuple, Optional

import librosa
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import soundfile as sf
import random

DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "training_checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "model_checkpoint.pt"
CAP_SECONDS_PER_CLASS = 7200.0
TARGET_SR = 16000
BATCH_SIZE = 16
EPOCHS = 12
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
POSSIBLE_CLASS_DIRS = ["real", "fake", "mixed"]
CLASS_LABELS = [name for name in POSSIBLE_CLASS_DIRS if (DATASET_ROOT / name).exists()]
if not CLASS_LABELS:
    raise RuntimeError(f"No class directories found in {DATASET_ROOT}. Expected one of: {POSSIBLE_CLASS_DIRS}")
NUM_CLASSES = len(CLASS_LABELS)


def scan_dataset(root: Path, cap_seconds: float) -> List[Tuple[Path, float, int]]:
    entries: List[Tuple[Path, float, int]] = []
    for label_idx, class_name in enumerate(CLASS_LABELS):
        class_dir = root / class_name
        if not class_dir.exists():
            continue

        accumulated = 0.0
        class_entries = []
        for file_path in sorted(class_dir.rglob("*.wav")):
            try:
                duration = float(librosa.get_duration(filename=str(file_path)))
            except Exception as exc:
                print(f"⚠️ Skipping corrupted audio metadata {file_path}: {exc}")
                continue

            if duration <= 0.0:
                continue

            if accumulated >= cap_seconds:
                break

            usable = min(duration, cap_seconds - accumulated)
            class_entries.append((file_path, usable, label_idx))
            accumulated += usable
            if accumulated >= cap_seconds:
                break

        entries.extend(class_entries)
        print(f"Loaded {len(class_entries)} {class_name} files totaling {accumulated/3600:.3f} hours")

    return entries


def extract_wave_features(path: Path, duration: float) -> torch.Tensor:
    y, sr = librosa.load(str(path), sr=TARGET_SR, mono=True, duration=float(duration))
    if y.size == 0 or sr <= 0:
        raise ValueError(f"Empty or invalid waveform from {path}")

    hop_length = max(1, int(0.0125 * sr))
    n_fft = max(256, int(0.025 * sr))

    n_mfcc = 20
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length, roll_percent=0.85)

    feature_vector = np.concatenate(
        [
            np.nanmean(mfcc, axis=1),
            np.nanstd(mfcc, axis=1),
            np.nanmean(delta, axis=1),
            np.nanstd(delta, axis=1),
            np.nanmean(delta2, axis=1),
            np.nanstd(delta2, axis=1),
            np.array([np.nanmean(centroid), np.nanstd(centroid)], dtype=np.float32),
            np.array([np.nanmean(rolloff), np.nanstd(rolloff)], dtype=np.float32),
        ],
        axis=0,
    ).astype(np.float32)

    feature_vector = np.nan_to_num(feature_vector, nan=0.0, posinf=0.0, neginf=0.0)
    expected_dim = n_mfcc * 6 + 4
    if feature_vector.ndim != 1:
        raise ValueError(f"Unexpected feature ndim {feature_vector.ndim} for {path}")
    if feature_vector.shape[0] != expected_dim:
        if feature_vector.shape[0] < expected_dim:
            padding = np.zeros(expected_dim - feature_vector.shape[0], dtype=np.float32)
            feature_vector = np.concatenate([feature_vector, padding], axis=0)
        else:
            feature_vector = feature_vector[:expected_dim]

    return torch.from_numpy(feature_vector)


class WaveFeatureDataset(Dataset):
    def __init__(self, entries: List[Tuple[Path, float, int]]):
        self.entries = entries

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int):
        path, duration, label = self.entries[index]
        try:
            features = extract_wave_features(path, duration)
            return features, torch.tensor(label, dtype=torch.long)
        except Exception as exc:
            raise RuntimeError(f"Failed to extract features from {path}: {exc}") from exc


class DeepfakeClassifier(nn.Module):
    def __init__(self, feature_dim: int, num_classes: int):
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(feature_dim, 128),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(128),
            nn.Dropout(0.25),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(64),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


def collate_valid_batch(batch):
    valid = [item for item in batch if item is not None]
    if not valid:
        raise ValueError("All batch entries are invalid; no valid waveform features available.")
    features, labels = zip(*valid)
    return torch.stack(features), torch.stack(labels)


def save_checkpoint(model: nn.Module, optimizer: torch.optim.Optimizer, epoch: int) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "class_labels": CLASS_LABELS,
        },
        CHECKPOINT_PATH,
    )
    print(f"💾 Saved checkpoint for epoch {epoch} at {CHECKPOINT_PATH}")


def load_checkpoint(model: nn.Module, optimizer: torch.optim.Optimizer) -> int:
    if not CHECKPOINT_PATH.exists():
        return 0

    checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
    checkpoint_labels = checkpoint.get("class_labels")
    saved_state = checkpoint.get("model_state_dict", {})
    if checkpoint_labels is not None and checkpoint_labels != CLASS_LABELS:
        print("⚠️ Checkpoint class labels differ from current dataset labels. Attempting partial weight load.")

    current_state = model.state_dict()
    matched_params = {}
    mismatched_keys = []
    for key, current_tensor in current_state.items():
        saved_tensor = saved_state.get(key)
        if saved_tensor is None:
            mismatched_keys.append(key)
            continue
        if saved_tensor.shape == current_tensor.shape:
            matched_params[key] = saved_tensor
        else:
            mismatched_keys.append(key)

    if matched_params:
        current_state.update(matched_params)
        model.load_state_dict(current_state)
        print(f"🔄 Loaded {len(matched_params)} compatible model parameters from checkpoint.")
    else:
        print("⚠️ No compatible model parameters found in checkpoint. Starting training from scratch.")

    if checkpoint_labels == CLASS_LABELS and "optimizer_state_dict" in checkpoint:
        try:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            print("🔄 Restored optimizer state from checkpoint.")
        except Exception as exc:
            print(f"⚠️ Failed to restore optimizer state: {exc}. Optimizer will be reinitialized.")
    else:
        print("⚠️ Optimizer state not restored due to class label mismatch or missing optimizer checkpoint.")

    start_epoch = int(checkpoint.get("epoch", 0)) + 1
    if mismatched_keys:
        print(f"⚠️ Skipped {len(mismatched_keys)} mismatched model parameters: {mismatched_keys}")
        start_epoch = 0
    else:
        print(f"🔄 Resuming from checkpoint at epoch {start_epoch}")
    return start_epoch


def build_feature_entries(entries: List[Tuple[Path, float, int]]) -> List[Tuple[Path, float, int]]:
    valid_entries = []
    for path, duration, label in entries:
        try:
            _ = extract_wave_features(path, duration)
            valid_entries.append((path, duration, label))
        except Exception as exc:
            print(f"⚠️ Skipping bad audio file {path}: {exc}")
    return valid_entries


def train() -> None:
    # Synthesize a 'mixed' class if absent so model can learn mixed real+AI segments
    def synthesize_mixed_dataset(root: Path, target_count: int = 500, seg_seconds: float = 2.0) -> None:
        mixed_dir = root / "mixed"
        mixed_dir.mkdir(parents=True, exist_ok=True)
        existing = list(mixed_dir.rglob("*.wav"))
        if existing:
            print(f"ℹ️ Mixed directory already has {len(existing)} files; skipping synthesis.")
            return

        real_files = list((root / "real").rglob("*.wav"))
        fake_files = list((root / "fake").rglob("*.wav"))
        if not real_files or not fake_files:
            print("⚠️ Not enough real/fake source files to synthesize mixed examples.")
            return

        sr = TARGET_SR
        L = int(seg_seconds * sr)
        print(f"🔬 Synthesizing {target_count} mixed examples (segment={seg_seconds}s) into {mixed_dir}")
        for i in range(target_count):
            r = random.choice(real_files)
            f = random.choice(fake_files)
            try:
                y_r, _ = librosa.load(str(r), sr=sr, mono=True)
                y_f, _ = librosa.load(str(f), sr=sr, mono=True)
            except Exception as exc:
                print(f"⚠️ Skipping pair due to load error: {exc}")
                continue

            def sample_segment(y: np.ndarray) -> np.ndarray:
                if y.shape[0] <= L:
                    return y
                start = random.randint(0, y.shape[0] - L)
                return y[start : start + L]

            seg_r = sample_segment(y_r)
            seg_f = sample_segment(y_f)
            # ensure both segments are the same length by padding shorter one with zeros
            if seg_r.shape[0] < L:
                seg_r = np.pad(seg_r, (0, L - seg_r.shape[0]), mode="constant")
            if seg_f.shape[0] < L:
                seg_f = np.pad(seg_f, (0, L - seg_f.shape[0]), mode="constant")

            alpha = random.uniform(0.3, 0.7)
            mixed = (1.0 - alpha) * seg_r[:L] + alpha * seg_f[:L]
            # normalize
            peak = max(1e-9, float(np.max(np.abs(mixed))))
            mixed = 0.95 * mixed / peak

            out_path = mixed_dir / f"mixed_{i}_{r.stem}_{f.stem}.wav"
            try:
                sf.write(str(out_path), mixed, sr)
            except Exception as exc:
                print(f"⚠️ Failed writing mixed file {out_path}: {exc}")

        print("✅ Mixed synthesis complete.")

    synthesize_mixed_dataset(DATASET_ROOT, target_count=500, seg_seconds=2.0)

    raw_entries = scan_dataset(DATASET_ROOT, CAP_SECONDS_PER_CLASS)
    if not raw_entries:
        raise RuntimeError(f"No audio files found in {DATASET_ROOT}")

    valid_entries = build_feature_entries(raw_entries)
    if not valid_entries:
        raise RuntimeError("No valid feature entries could be built from the dataset.")

    print(f"✅ Built {len(valid_entries)} valid feature entries from the dataset.")
    dataset = WaveFeatureDataset(valid_entries)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_valid_batch)

    sample_feature, _ = dataset[0]
    model = DeepfakeClassifier(feature_dim=sample_feature.shape[0], num_classes=NUM_CLASSES).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    start_epoch = load_checkpoint(model, optimizer)
    try:
        for epoch in range(start_epoch, EPOCHS):
            model.train()
            epoch_loss = 0.0
            processed = 0

            for batch_idx, batch in enumerate(dataloader, start=1):
                try:
                    features, labels = batch
                    features = features.to(DEVICE)
                    labels = labels.to(DEVICE)

                    optimizer.zero_grad()
                    logits = model(features)
                    loss = criterion(logits, labels)
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item() * features.size(0)
                    processed += features.size(0)
                except Exception as exc:
                    print(f"⚠️ Skipping bad batch {batch_idx} at epoch {epoch}: {exc}")
                    continue

            if processed == 0:
                print(f"⚠️ No valid samples processed for epoch {epoch}.")
                continue

            average_loss = epoch_loss / processed
            print(f"Epoch {epoch+1}/{EPOCHS} | loss={average_loss:.6f} | processed_samples={processed}")

            save_checkpoint(model, optimizer, epoch)

        print("✅ Training complete.")
    except KeyboardInterrupt:
        print("⏹ KeyboardInterrupt received. Saving checkpoint and stopping gracefully.")
        save_checkpoint(model, optimizer, epoch)
    except Exception as exc:
        print(f"❌ Training interrupted by exception: {exc}")
        save_checkpoint(model, optimizer, epoch)
        raise


if __name__ == "__main__":
    train()
