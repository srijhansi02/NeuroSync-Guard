import json
import os
import random
from pathlib import Path
from typing import List, Tuple

import librosa
import numpy as np
import torch
import torch.nn as nn
from torch.nn.functional import softmax

DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "training_checkpoints" / "model_checkpoint.pt"
ERROR_REPORT_PATH = Path(__file__).resolve().parent / "terminal_error_report.json"
TARGET_SR = 16000
NUM_SAMPLES_PER_CLASS = 10
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

    def forward(self, acoustic_input: torch.Tensor, semantic_input: torch.Tensor):
        acoustic_hidden = self.acoustic_branch(acoustic_input)
        semantic_hidden = self.semantic_branch(semantic_input)
        combined = torch.cat([acoustic_hidden, semantic_hidden], dim=1)
        fused = self.shared(combined)
        return self.head_acoustic(fused), self.head_semantic(fused)


def text_to_vector(text: str) -> torch.Tensor:
    vector = np.zeros(VOCAB_SIZE, dtype=np.float32)
    for token in text.lower().split():
        if token in VOCAB:
            vector[VOCAB[token]] += 1.0
    return torch.tensor(vector, dtype=torch.float32)


def extract_segmentation_features(audio_path: Path) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    y, sr = librosa.load(str(audio_path), sr=TARGET_SR, mono=True)
    if sr <= 0 or y.size == 0:
        raise ValueError(f"Invalid audio file: {audio_path}")

    frame_len = int(0.020 * sr)
    hop_len = frame_len
    n_fft = int(0.040 * sr)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=n_fft, hop_length=hop_len)
    delta = librosa.feature.delta(mfcc)
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    f0_values = f0[~np.isnan(f0)]
    f0_mean = float(np.mean(f0_values)) if f0_values.size else 0.0
    f0_var = float(np.var(f0_values)) if f0_values.size else 0.0
    f0_voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag.size else 0.0

    acoustic_vector = np.concatenate(
        [
            np.mean(mfcc, axis=1),
            np.std(mfcc, axis=1),
            np.mean(delta, axis=1),
            np.std(delta, axis=1),
            np.array([f0_mean, f0_var, f0_voiced_ratio], dtype=np.float32),
        ]
    )
    return torch.tensor(acoustic_vector, dtype=torch.float32), torch.tensor([f0_mean, f0_var, f0_voiced_ratio], dtype=torch.float32), torch.tensor(delta.mean(axis=1), dtype=torch.float32)


def load_checkpoint(model: DualHeadClassifier, device: torch.device) -> Tuple[DualHeadClassifier, int]:
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(f"Checkpoint not found at {CHECKPOINT_PATH}")

    checkpoint = torch.load(CHECKPOINT_PATH, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    epoch = checkpoint.get("epoch", 0)
    return model, epoch


def scan_training_paths(root: Path, cap_seconds: float) -> List[Path]:
    used_paths: List[Path] = []
    for group_name in ["real", "fake"]:
        group_dir = root / group_name
        if not group_dir.exists():
            continue
        cumulative_seconds = 0.0
        for wav_path in sorted(group_dir.rglob("*.wav")):
            duration = float(librosa.get_duration(filename=str(wav_path)))
            if duration <= 0.0:
                continue
            if cumulative_seconds >= cap_seconds:
                break
            cumulative_seconds += min(duration, cap_seconds - cumulative_seconds)
            used_paths.append(wav_path)
            if cumulative_seconds >= cap_seconds:
                break
    return used_paths


def choose_holdout_samples(root: Path, excluded_paths: List[Path], num_per_class: int) -> List[Tuple[Path, int, str]]:
    selected = []
    for group_name, label in [("real", 0), ("fake", 1)]:
        group_dir = root / group_name
        if not group_dir.exists():
            continue
        candidates = [p for p in sorted(group_dir.rglob("*.wav")) if p not in excluded_paths]
        if len(candidates) < num_per_class:
            candidates = [p for p in sorted(group_dir.rglob("*.wav"))]
        chosen = random.sample(candidates, min(num_per_class, len(candidates)))
        for path in chosen:
            transcript = random.choice(SCAM_TEXTS if label == 1 else SAFE_TEXTS)
            selected.append((path, label, transcript))
    return selected


def build_profile(acoustic_prob: float, semantic_prob: float) -> str:
    acoustic_profile = "Deepfake" if acoustic_prob >= 0.5 else "Real"
    semantic_profile = "Fraud" if semantic_prob >= 0.5 else "Safe"
    return f"{acoustic_profile} / {semantic_profile}"


def write_error_report(error: Exception, context: dict) -> None:
    data = {
        "error_type": type(error).__name__,
        "message": str(error),
        "context": context,
    }
    with open(ERROR_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main() -> None:
    try:
        random.seed(42)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if not DATASET_ROOT.exists():
            raise FileNotFoundError(f"Dataset root not found: {DATASET_ROOT}")
        if not CHECKPOINT_PATH.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {CHECKPOINT_PATH}")

        used_paths = scan_training_paths(DATASET_ROOT, 7200.0)
        holdouts = choose_holdout_samples(DATASET_ROOT, used_paths, NUM_SAMPLES_PER_CLASS)
        print(f"Selected {len(holdouts)} holdout samples for validation.")

        sample_acoustic, sample_semantic, _ = extract_segmentation_features(holdouts[0][0])
        acoustic_dim = sample_acoustic.shape[0]
        semantic_dim = VOCAB_SIZE

        model = DualHeadClassifier(acoustic_dim=acoustic_dim, semantic_dim=semantic_dim)
        model, checkpoint_epoch = load_checkpoint(model, device)
        model.to(device)
        model.eval()

        results = []
        correct_acoustic = 0
        total_real = 0
        total_fake = 0
        false_positives = 0
        false_negatives = 0

        for sample_path, true_label, transcript in holdouts:
            acoustic_features, f0_features, delta_mean = extract_segmentation_features(sample_path)
            semantic_features = text_to_vector(transcript)

            acoustic_tensor = acoustic_features.unsqueeze(0).to(device)
            semantic_tensor = semantic_features.unsqueeze(0).to(device)

            with torch.no_grad():
                logits_acoustic, logits_semantic = model(acoustic_tensor, semantic_tensor)
                probs_acoustic = softmax(logits_acoustic, dim=1).cpu().numpy()[0]
                probs_semantic = softmax(logits_semantic, dim=1).cpu().numpy()[0]

            acoustic_prob = float(probs_acoustic[1])
            semantic_prob = float(probs_semantic[1])
            acoustic_pred = int(acoustic_prob >= 0.5)
            semantic_pred = int(semantic_prob >= 0.5)

            if true_label == 0:
                total_real += 1
                if acoustic_pred == 1:
                    false_positives += 1
            else:
                total_fake += 1
                if acoustic_pred == 0:
                    false_negatives += 1

            if acoustic_pred == true_label:
                correct_acoustic += 1

            results.append(
                {
                    "path": str(sample_path.relative_to(DATASET_ROOT)),
                    "ground_truth": "fake" if true_label == 1 else "real",
                    "predicted_profile": build_profile(acoustic_prob, semantic_prob),
                    "acoustic_prob": round(acoustic_prob, 4),
                    "semantic_prob": round(semantic_prob, 4),
                    "transcript": transcript,
                }
            )

        overall_accuracy = correct_acoustic / max(1, len(results))
        false_positive_rate = false_positives / max(1, total_real)
        false_negative_rate = false_negatives / max(1, total_fake)

        print("\n=== NeuroSync-Guard Validation Scoreboard ===")
        print(f"Checkpoint epoch: {checkpoint_epoch}")
        print(f"Samples evaluated: {len(results)}")
        print(f"Overall Acoustic Accuracy: {overall_accuracy:.3f}")
        print(f"False Positive Rate (real -> fake): {false_positive_rate:.3f}")
        print(f"False Negative Rate (fake -> real): {false_negative_rate:.3f}")
        print("-----------------------------------------------")
        for entry in results:
            print(
                f"{entry['path']} | GT: {entry['ground_truth']} | Profile: {entry['predicted_profile']} | "
                f"AcousticProb: {entry['acoustic_prob']} | SemanticProb: {entry['semantic_prob']}"
            )

    except Exception as exc:
        context = {
            "checkpoint_path": str(CHECKPOINT_PATH),
            "dataset_root": str(DATASET_ROOT),
            "script": "test.py",
        }
        write_error_report(exc, context)
        print(f"Error occurred: {exc}")
        print(f"Wrote detailed error report to {ERROR_REPORT_PATH}")


if __name__ == "__main__":
    main()
