import argparse
from pathlib import Path
from typing import List, Tuple

import librosa
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "training_checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "model_checkpoint.pt"
CAP_SECONDS_PER_CLASS = 7200.0
TARGET_SR = 16000
BATCH_SIZE = 32
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def scan_dataset(root: Path, cap_seconds: float) -> List[Tuple[Path, float, int]]:
    entries: List[Tuple[Path, float, int]] = []
    for class_name, label in [("real", 0), ("fake", 1)]:
        class_dir = root / class_name
        if not class_dir.exists():
            continue

        accumulated = 0.0
        for file_path in sorted(class_dir.rglob("*.wav")):
            try:
                duration = float(librosa.get_duration(path=str(file_path)))
            except Exception as exc:
                print(f"⚠️ Skipping corrupted metadata for {file_path}: {exc}")
                continue

            if duration <= 0.0:
                continue

            if accumulated >= cap_seconds:
                break

            usable = min(duration, cap_seconds - accumulated)
            entries.append((file_path, usable, label))
            accumulated += usable
            if accumulated >= cap_seconds:
                break

        print(f"Loaded {len([item for item in entries if item[2] == label])} {class_name} files totaling {accumulated/3600:.3f} hours")

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

    if feature_vector.ndim != 1:
        raise ValueError(f"Unexpected feature ndim {feature_vector.ndim} for {path}")

    expected_dim = n_mfcc * 6 + 4
    if feature_vector.shape[0] != expected_dim:
        if feature_vector.shape[0] < expected_dim:
            padding = np.zeros(expected_dim - feature_vector.shape[0], dtype=np.float32)
            feature_vector = np.concatenate([feature_vector, padding], axis=0)
        else:
            feature_vector = feature_vector[:expected_dim]

    if np.isnan(feature_vector).any() or np.isinf(feature_vector).any():
        raise ValueError(f"Invalid numeric values found in feature vector for {path}")

    return torch.from_numpy(feature_vector)


class WaveFeatureDataset(Dataset):
    def __init__(self, entries: List[Tuple[Path, float, int]]):
        self.entries = entries

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int):
        path, duration, label = self.entries[index]
        features = extract_wave_features(path, duration)
        return features, torch.tensor([label], dtype=torch.float32)


class DeepfakeBinaryClassifier(nn.Module):
    def __init__(self, feature_dim: int):
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
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


def evaluate_predictions(predictions: np.ndarray, labels: np.ndarray) -> dict:
    assert predictions.shape == labels.shape
    preds = (predictions >= 0.0).astype(np.int32)
    labels = labels.astype(np.int32)

    tp = int(((preds == 1) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    total = tp + tn + fp + fn

    accuracy = (tp + tn) / max(total, 1)
    precision = tp / max((tp + fp), 1)
    recall = tp / max((tp + fn), 1)
    f1 = 2 * precision * recall / max((precision + recall), 1e-9)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "total": total,
    }


def main(checkpoint_path: Path, dataset_root: Path, cap_seconds: float) -> None:
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    entries = scan_dataset(dataset_root, cap_seconds)
    if not entries:
        raise RuntimeError(f"No audio files found in {dataset_root}")

    dataset = WaveFeatureDataset(entries)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)

    sample_feature, _ = dataset[0]
    model = DeepfakeBinaryClassifier(feature_dim=sample_feature.shape[0]).to(DEVICE)
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    all_logits = []
    all_labels = []
    loss_fn = nn.BCEWithLogitsLoss()
    total_loss = 0.0
    total_samples = 0

    with torch.no_grad():
        for features, labels in dataloader:
            features = features.to(DEVICE)
            labels = labels.to(DEVICE)
            logits = model(features)
            loss = loss_fn(logits, labels)
            total_loss += loss.item() * features.size(0)
            total_samples += features.size(0)
            all_logits.append(logits.cpu().numpy().flatten())
            all_labels.append(labels.cpu().numpy().flatten())

    logits = np.concatenate(all_logits, axis=0)
    labels = np.concatenate(all_labels, axis=0)
    metrics = evaluate_predictions(logits, labels)
    average_loss = total_loss / max(total_samples, 1)

    print("✅ Deepfake detector evaluation complete")
    print(f"Data samples evaluated: {total_samples}")
    print(f"Validation loss: {average_loss:.6f}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall: {metrics['recall']:.4f}")
    print(f"F1 score: {metrics['f1_score']:.4f}")
    print(f"TP: {metrics['tp']}  TN: {metrics['tn']}  FP: {metrics['fp']}  FN: {metrics['fn']}")

    output_path = Path("evaluation_results.csv")
    np.savetxt(
        output_path,
        np.stack([labels, logits], axis=1),
        delimiter=",",
        header="label,logit",
        comments="",
    )
    print(f"Saved raw predictions to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the NeuroSync deepfake detector checkpoint.")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=CHECKPOINT_PATH,
        help="Path to the model checkpoint file.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DATASET_ROOT,
        help="Path to the local deepfake_audio_dataset_jay15k dataset.",
    )
    parser.add_argument(
        "--cap-seconds",
        type=float,
        default=CAP_SECONDS_PER_CLASS,
        help="Per-class duration cap in seconds.",
    )
    args = parser.parse_args()
    main(args.checkpoint, args.dataset_root, args.cap_seconds)
