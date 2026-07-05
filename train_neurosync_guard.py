import os
import math
from pathlib import Path
from typing import List, Dict, Tuple

import librosa
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModel,
    AutoTokenizer,
    Wav2Vec2Model,
    Wav2Vec2Processor,
)

DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "training_checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "checkpoint.pt"
CAP_SECONDS_PER_CLASS = 7200.0
TARGET_SR = 16000
BATCH_SIZE = 2
EPOCHS = 3
LEARNING_RATE = 2e-5
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def scan_dataset_by_duration(root: Path, max_seconds: float) -> Dict[str, List[Tuple[Path, float, bool]]]:
    selected: Dict[str, List[Tuple[Path, float, bool]]] = {"real": [], "fake": []}

    for label in ["real", "fake"]:
        folder = root / label
        if not folder.exists():
            continue

        cumulative_seconds = 0.0
        for wav_path in sorted(folder.rglob("*.wav")):
            duration = float(librosa.get_duration(filename=str(wav_path)))
            if duration <= 0.0:
                continue

            if cumulative_seconds >= max_seconds:
                break

            remaining = max_seconds - cumulative_seconds
            if duration > remaining:
                selected[label].append((wav_path, remaining, True))
                cumulative_seconds = max_seconds
                break

            selected[label].append((wav_path, duration, False))
            cumulative_seconds += duration

        print(
            f"Loaded {len(selected[label])} {label} files, totaling {cumulative_seconds / 3600:.3f} hours (target {max_seconds / 3600:.3f}h)."
        )

    return selected


def extract_pitch_features(y: np.ndarray, sr: int) -> torch.Tensor:
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        voiced = f0[~np.isnan(f0)]
        mean_f0 = float(np.mean(voiced)) if voiced.size else 0.0
        var_f0 = float(np.var(voiced)) if voiced.size else 0.0
        voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag.size else 0.0
        urgency = float(min(1.0, voiced_ratio + var_f0 / 500.0))
    except Exception:
        mean_f0 = 0.0
        var_f0 = 0.0
        voiced_ratio = 0.0
        urgency = 0.0

    return torch.tensor([mean_f0 / 500.0, var_f0 / 2000.0, voiced_ratio, urgency], dtype=torch.float32)


class NeuroSyncGuardDataset(Dataset):
    def __init__(self, entries: List[Tuple[Path, float, bool]], processor: Wav2Vec2Processor, tokenizer: AutoTokenizer):
        self.entries = entries
        self.processor = processor
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        wav_path, duration, is_partial = self.entries[idx]
        load_kwargs = {"sr": TARGET_SR, "mono": True}
        if is_partial:
            load_kwargs["duration"] = float(duration)

        y, sr = librosa.load(str(wav_path), **load_kwargs)
        audio_inputs = self.processor(y, sampling_rate=sr, return_tensors="pt", padding=True)

        semantic_text = "urgent scam attempt" if wav_path.parts[-3].lower() == "fake" else "calm human conversation"
        semantic_inputs = self.tokenizer(
            semantic_text,
            padding="max_length",
            truncation=True,
            max_length=16,
            return_tensors="pt",
        )

        pitch_features = extract_pitch_features(y, sr)
        label = 1 if wav_path.parts[-3].lower() == "fake" else 0

        return {
            "input_values": audio_inputs.input_values.squeeze(0),
            "audio_attention_mask": audio_inputs.attention_mask.squeeze(0),
            "semantic_input_ids": semantic_inputs.input_ids.squeeze(0),
            "semantic_attention_mask": semantic_inputs.attention_mask.squeeze(0),
            "pitch_features": pitch_features,
            "labels": torch.tensor(label, dtype=torch.long),
        }


class DualFusionModel(nn.Module):
    def __init__(self, audio_model: Wav2Vec2Model, text_model: AutoModel, hidden_size: int = 256):
        super().__init__()
        self.audio_model = audio_model
        self.text_model = text_model
        self.fusion = nn.Sequential(
            nn.Linear(self.audio_model.config.hidden_size + self.text_model.config.hidden_size + 4, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, 2),
        )

    def forward(
        self,
        input_values: torch.Tensor,
        audio_attention_mask: torch.Tensor,
        semantic_input_ids: torch.Tensor,
        semantic_attention_mask: torch.Tensor,
        pitch_features: torch.Tensor,
    ) -> torch.Tensor:
        audio_outputs = self.audio_model(input_values=input_values, attention_mask=audio_attention_mask)
        audio_emb = audio_outputs.last_hidden_state.mean(dim=1)

        text_outputs = self.text_model(input_ids=semantic_input_ids, attention_mask=semantic_attention_mask)
        text_emb = text_outputs.last_hidden_state[:, 0, :]

        fusion_input = torch.cat([audio_emb, text_emb, pitch_features], dim=1)
        return self.fusion(fusion_input)


def build_model() -> Tuple[DualFusionModel, Wav2Vec2Processor, AutoTokenizer]:
    processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    audio_model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base")
    text_model = AutoModel.from_pretrained("distilbert-base-uncased")

    model = DualFusionModel(audio_model=audio_model, text_model=text_model)
    return model, processor, tokenizer


def load_checkpoint(model: DualFusionModel, optimizer: torch.optim.Optimizer) -> int:
    if not CHECKPOINT_PATH.exists():
        return 0

    checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    start_epoch = checkpoint.get("epoch", 0) + 1
    print("🔄 Found existing training state tracker. Continuing model training from the last saved epoch/step index...")
    return start_epoch


def save_checkpoint(model: DualFusionModel, optimizer: torch.optim.Optimizer, epoch: int) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        CHECKPOINT_PATH,
    )
    print(f"💾 Saved epoch {epoch} checkpoint to {CHECKPOINT_PATH}")


def collate_fn(batch: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
    return {
        "input_values": nn.utils.rnn.pad_sequence([item["input_values"] for item in batch], batch_first=True),
        "audio_attention_mask": nn.utils.rnn.pad_sequence([item["audio_attention_mask"] for item in batch], batch_first=True),
        "semantic_input_ids": torch.stack([item["semantic_input_ids"] for item in batch]),
        "semantic_attention_mask": torch.stack([item["semantic_attention_mask"] for item in batch]),
        "pitch_features": torch.stack([item["pitch_features"] for item in batch]),
        "labels": torch.stack([item["labels"] for item in batch]),
    }


def train():
    print(f"📁 Scanning dataset root: {DATASET_ROOT}")
    budgets = scan_dataset_by_duration(DATASET_ROOT, CAP_SECONDS_PER_CLASS)

    real_entries = budgets.get("real", [])
    fake_entries = budgets.get("fake", [])
    all_entries = real_entries + fake_entries
    total_seconds = sum(entry[1] for entry in all_entries)
    print(f"⏱️ Total selected audio loaded for training: {total_seconds / 3600:.3f} hours")

    model, processor, tokenizer = build_model()
    model.to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    start_epoch = load_checkpoint(model, optimizer)
    if start_epoch == 0:
        print("⚙️ Starting training from base model configuration.")

    dataset = NeuroSyncGuardDataset(all_entries, processor, tokenizer)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)

    for epoch in range(start_epoch, EPOCHS):
        model.train()
        epoch_loss = 0.0
        for batch_idx, batch in enumerate(dataloader, start=1):
            input_values = batch["input_values"].to(DEVICE)
            audio_mask = batch["audio_attention_mask"].to(DEVICE)
            semantic_ids = batch["semantic_input_ids"].to(DEVICE)
            semantic_mask = batch["semantic_attention_mask"].to(DEVICE)
            pitch_features = batch["pitch_features"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            logits = model(
                input_values=input_values,
                audio_attention_mask=audio_mask,
                semantic_input_ids=semantic_ids,
                semantic_attention_mask=semantic_mask,
                pitch_features=pitch_features,
            )

            loss = criterion(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            if batch_idx % 5 == 0:
                print(
                    f"Epoch {epoch + 1}/{EPOCHS} | Batch {batch_idx}/{len(dataloader)} | Loss: {loss.item():.4f}"
                )

        avg_loss = epoch_loss / max(1, len(dataloader))
        print(f"✅ Epoch {epoch + 1} complete. Average loss: {avg_loss:.4f}")
        save_checkpoint(model, optimizer, epoch)

    print("🏁 Training complete. Final checkpoint saved.")


if __name__ == "__main__":
    train()
