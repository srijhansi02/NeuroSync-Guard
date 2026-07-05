import os
import tempfile
import base64
import json
from datetime import datetime
from uuid import uuid4
from pathlib import Path
import urllib.request
import urllib.error

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

import librosa
import numpy as np
import torch
import torch.nn as nn

app = Flask(__name__)
CORS(app)

MODEL_CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "training_checkpoints", "model_checkpoint.pt")
DATASET_ROOT = Path(__file__).resolve().parent / "deepfake_audio_dataset_jay15k"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
TARGET_SR = 16000
EXPECTED_FEATURE_DIM = 20 * 6 + 4
WINDOW_LENGTH_SECONDS = 2.0
WINDOW_HOP_SECONDS = 1.0
MODEL_CLASS_LABELS = None

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


def load_model() -> tuple[torch.nn.Module, bool, list[str] | None]:
    global MODEL_CLASS_LABELS
    model = DeepfakeBinaryClassifier(feature_dim=EXPECTED_FEATURE_DIM).to(DEVICE)
    loaded = False
    class_labels = None

    if not os.path.exists(MODEL_CHECKPOINT_PATH):
        print(f"CRITICAL: Custom trained weights not found at {MODEL_CHECKPOINT_PATH}. Please train the model and place the checkpoint there.")
        return model, loaded, class_labels

    try:
        checkpoint = torch.load(MODEL_CHECKPOINT_PATH, map_location=DEVICE)
        class_labels = checkpoint.get("class_labels")
        if class_labels and len(class_labels) > 1:
            model = DeepfakeClassifier(feature_dim=EXPECTED_FEATURE_DIM, num_classes=len(class_labels)).to(DEVICE)
            MODEL_CLASS_LABELS = class_labels
            print(f"✅ Loaded multi-class model with labels: {class_labels}")
        else:
            model = DeepfakeBinaryClassifier(feature_dim=EXPECTED_FEATURE_DIM).to(DEVICE)
            MODEL_CLASS_LABELS = None
            print("✅ Loaded binary deepfake model")

        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        loaded = True
        print(f"✅ Loaded custom trained weights from {MODEL_CHECKPOINT_PATH}")
    except Exception as exc:
        print(f"CRITICAL: Failed to load model checkpoint from {MODEL_CHECKPOINT_PATH}: {exc}")

    return model, loaded, class_labels

MODEL, MODEL_LOADED, MODEL_CLASS_LABELS = load_model()


def scan_dataset(root: Path):
    entries = []
    for label in ["real", "fake"]:
        class_dir = root / label
        if not class_dir.exists():
            continue

        for file_path in sorted(class_dir.rglob("*.wav")):
            try:
                duration = float(librosa.get_duration(path=str(file_path)))
            except Exception:
                continue

            entries.append({
                "path": file_path,
                "label": label,
                "duration": duration,
            })

    return entries


DATASET_POOL = scan_dataset(DATASET_ROOT)
HISTORY_FILE = Path(__file__).resolve().parent / "analysis_history.json"
MAX_HISTORY_ITEMS = 100


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def append_history(record):
    history = load_history()
    history.insert(0, record)
    history = history[:MAX_HISTORY_ITEMS]
    save_history(history)
    return history


def allow_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response

app.after_request(allow_cors)


# ============ GEMINI SEMANTIC ANALYSIS ============

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

def transcribe_audio_placeholder(audio_path: str) -> str:
    """Fallback: return a placeholder transcript."""
    return "[Audio content placeholder - transcription failed]"

def transcribe_audio_with_whisper(audio_path: str) -> str:
    """
    Free open-source transcription using OpenAI Whisper model.
    Runs locally - no API costs.
    """
    try:
        from transformers import pipeline
        import librosa
        
        # Load audio at 16kHz (Whisper requirement)
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        
        # Load Whisper model (downloads on first use, cached afterward)
        transcriber = pipeline("automatic-speech-recognition", model="openai/whisper-base")
        
        # Transcribe
        result = transcriber(audio, chunk_length_s=30, batch_size=4)
        transcript = result.get("text", "").strip()
        
        return transcript if transcript else "[Audio transcribed but no speech detected]"
    except Exception as e:
        print(f"⚠️ Whisper transcription error: {e}")
        return transcribe_audio_placeholder(audio_path)

def transcribe_audio_with_google_speech(audio_path: str) -> str:
    """
    Google Cloud Speech-to-Text (requires credentials - kept for backward compatibility).
    Prefer transcribe_audio_with_whisper for free transcription.
    """
    try:
        from google.cloud import speech
        client = speech.SpeechClient()
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
        )
        response = client.recognize(config=config, audio=audio)
        transcript = " ".join([r.alternatives[0].transcript for r in response.results if r.results])
        return transcript if transcript else transcribe_audio_placeholder(audio_path)
    except Exception:
        return transcribe_audio_placeholder(audio_path)

def analyze_with_gemini(transcript: str, acoustic_prediction: str, anomaly_score: float) -> dict:
    """
    Send transcript + acoustic context to Gemini for semantic scam/fraud analysis.
    Returns structured semantic risk assessment covering many scam types.
    """
    if not GEMINI_API_KEY:
        return get_semantic_analysis_heuristic(transcript, acoustic_prediction, anomaly_score)
    
    try:
        prompt = f"""You are an expert fraud and scam detection analyst. Analyze the following call transcript for ALL types of scams, fraud, social engineering, and manipulation tactics.

Transcript: "{transcript}"

Acoustic Detection Result: {acoustic_prediction}
Voice Anomaly Score: {anomaly_score:.2f}

Analyze for these scam categories:
- Financial Scams (banking, wire transfers, cryptocurrency, investment schemes, loan scams)
- Tech Support Scams (fake Microsoft/Apple/antivirus support)
- Impersonation Scams (police, IRS, government, utilities)
- Romance/Dating Scams (emotional manipulation, fake relationships)
- Prize/Lottery Scams (won money they didn't enter)
- Charity Scams (fake donations)
- Job/Employment Scams (fake job offers, payment required)
- Rental/Real Estate Scams (fake listings, advance payment)
- Delivery Scams (package delivery issues, suspicious tracking)
- Healthcare/Pharmacy Scams (fake prescriptions, health insurance)
- Social Media Impersonation (fake profiles, verification)
- Account Takeover Attempts (password resets, 2FA bypasses)
- Tax Scams (fake IRS, tax refunds)
- Insurance Scams (fake claims, inflated costs)
- Extortion/Blackmail (threats, sextortion, leaked data)
- Grandparent Scams (family emergency, money needed)
- Car/Vehicle Scams (accidents, roadside assistance)
- Utility/Service Scams (power company, water company threats)

Respond ONLY with valid JSON (no markdown, no code blocks, no explanation):
{{
  "risk_level": "Low|Medium|High|Critical",
  "scam_indicators": ["indicator1", "indicator2", "indicator3"],
  "fraud_category": "Financial Scam|Tech Support|Impersonation|Romance|Prize/Lottery|Charity|Job/Employment|Rental|Delivery|Healthcare|Social Media|Account Takeover|Tax|Insurance|Extortion|Grandparent|Vehicle|Utility|Other|None",
  "explanation": "Specific evidence from the transcript supporting this classification",
  "combined_risk_score": 0.0-1.0
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        if 'candidates' in result and len(result['candidates']) > 0:
            text_content = result['candidates'][0]['content']['parts'][0]['text']
            try:
                parsed = json.loads(text_content)
                return {
                    "semantic_available": True,
                    "risk_level": parsed.get("risk_level", "Unknown"),
                    "scam_indicators": parsed.get("scam_indicators", []),
                    "fraud_category": parsed.get("fraud_category", "None"),
                    "explanation": parsed.get("explanation", ""),
                    "combined_risk_score": float(parsed.get("combined_risk_score", 0.0))
                }
            except json.JSONDecodeError:
                return get_semantic_analysis_heuristic(transcript, acoustic_prediction, anomaly_score)
        
        return get_semantic_analysis_heuristic(transcript, acoustic_prediction, anomaly_score)
    except Exception as e:
        print(f"⚠️ Gemini API error: {e}. Falling back to heuristic.")
        return get_semantic_analysis_heuristic(transcript, acoustic_prediction, anomaly_score)

def get_semantic_analysis_heuristic(transcript: str, acoustic_prediction: str, anomaly_score: float) -> dict:
    """
    Comprehensive fallback heuristic for semantic risk detection.
    Detects many types of scams without relying on Gemini API.
    """
    transcript_lower = (transcript or "").lower()
    
    red_flags = []
    fraud_category = "None"
    risk_level = "Low"
    
    # Urgency & Pressure Tactics
    urgency_keywords = ["urgent", "immediate", "now", "hurry", "quickly", "asap", "right now", "today", "this moment", "don't delay"]
    
    # Financial & Banking Scams
    financial_keywords = ["bank", "account", "password", "otp", "pin", "cvv", "card", "transfer", "money", "wire", "bitcoin", "crypto", "investment", "loan", "credit"]
    
    # Tech Support Scams
    tech_support_keywords = ["tech support", "microsoft", "apple", "windows", "computer", "virus", "malware", "update", "antivirus", "remote", "support"]
    
    # Impersonation (Government, Police, IRS, etc.)
    government_keywords = ["calling from", "i'm", "im", "this is", "officer", "agent", "representative", "government", "irs", "police", "sheriff", "federal", "tax"]
    
    # Romance & Dating Scams
    romance_keywords = ["love", "sweetheart", "darling", "dear", "dating", "relationship", "lonely", "travel", "meet you", "special someone", "overseas"]
    
    # Prize/Lottery Scams
    prize_keywords = ["congratulations", "won", "lottery", "prize", "jackpot", "lucky", "selected", "claimed", "refund", "tax refund"]
    
    # Charity/Donation Scams
    charity_keywords = ["donation", "charity", "relief fund", "disaster", "help", "contribute", "cause", "nonprofit"]
    
    # Job/Employment Scams
    job_keywords = ["job", "employment", "position", "hiring", "interview", "salary", "payment", "deposit", "advance payment", "processing fee"]
    
    # Rental/Real Estate Scams
    rental_keywords = ["apartment", "rental", "property", "house", "lease", "tenant", "landlord", "deposit", "availability"]
    
    # Delivery/Package Scams
    delivery_keywords = ["delivery", "package", "tracking", "shipped", "fedex", "ups", "amazon", "recipient", "signature", "address"]
    
    # Healthcare/Pharmacy Scams
    healthcare_keywords = ["pharmacy", "prescription", "medication", "doctor", "insurance", "health", "treatment", "medical", "billing"]
    
    # Grandparent Scams
    grandparent_keywords = ["grandpa", "grandma", "grandson", "granddaughter", "family emergency", "accident", "hospital", "jail", "bail"]
    
    # Extortion/Threats
    extortion_keywords = ["blackmail", "leak", "expose", "photo", "video", "sextortion", "threat", "crime", "arrest", "lawsuit"]
    
    # Account Takeover/Verification
    account_keywords = ["verify", "confirmation", "unusual activity", "suspicious", "reset password", "2fa", "two factor", "authenticate"]
    
    # Social Media/Platform Scams
    social_keywords = ["facebook", "instagram", "twitter", "tiktok", "snapchat", "verification badge", "follow", "follower"]
    
    # Tax Scams
    tax_keywords = ["refund", "tax", "irs", "revenue", "audit", "deduction"]
    
    # Utility/Service Provider Scams
    utility_keywords = ["power company", "utility", "electricity", "water", "gas", "service", "bill", "disconnection", "late payment"]
    
    # Car/Vehicle Scams
    vehicle_keywords = ["car", "vehicle", "accident", "insurance", "roadside", "tow", "repair", "damage", "claim"]
    
    # Detect patterns
    if any(kw in transcript_lower for kw in urgency_keywords):
        red_flags.append("Urgency/Pressure")
        risk_level = "High" if risk_level == "Low" else risk_level
    
    # Financial Scams
    if any(kw in transcript_lower for kw in financial_keywords):
        red_flags.append("Financial Data Request")
        fraud_category = "Financial Scam"
        risk_level = "Critical" if any(x in transcript_lower for x in ["password", "otp", "cvv", "wire", "transfer"]) else "High"
    
    # Tech Support Scams
    elif any(kw in transcript_lower for kw in tech_support_keywords):
        red_flags.append("Tech Support Claim")
        fraud_category = "Tech Support"
        risk_level = "High"
    
    # Government Impersonation
    elif any(kw in transcript_lower for kw in government_keywords):
        red_flags.append("Government Impersonation")
        fraud_category = "Impersonation"
        risk_level = "High"
    
    # Romance Scams
    elif any(kw in transcript_lower for kw in romance_keywords):
        red_flags.append("Romance/Relationship Appeal")
        fraud_category = "Romance Scam"
        risk_level = "High"
    
    # Prize/Lottery Scams
    elif any(kw in transcript_lower for kw in prize_keywords):
        red_flags.append("Unexpected Prize/Winning")
        fraud_category = "Prize/Lottery Scam"
        risk_level = "High"
    
    # Charity Scams
    elif any(kw in transcript_lower for kw in charity_keywords):
        red_flags.append("Charity/Donation Request")
        fraud_category = "Charity Scam"
        risk_level = "Medium"
    
    # Job/Employment Scams
    elif any(kw in transcript_lower for kw in job_keywords):
        red_flags.append("Job/Employment Offer")
        fraud_category = "Job/Employment Scam"
        risk_level = "High" if any(x in transcript_lower for x in ["advance payment", "deposit", "processing fee"]) else "Medium"
    
    # Rental/Real Estate Scams
    elif any(kw in transcript_lower for kw in rental_keywords):
        red_flags.append("Rental/Property Offer")
        fraud_category = "Rental Scam"
        risk_level = "Medium"
    
    # Delivery Scams
    elif any(kw in transcript_lower for kw in delivery_keywords):
        red_flags.append("Delivery/Package Issue")
        fraud_category = "Delivery Scam"
        risk_level = "Medium"
    
    # Healthcare Scams
    elif any(kw in transcript_lower for kw in healthcare_keywords):
        red_flags.append("Healthcare/Pharmacy Claim")
        fraud_category = "Healthcare Scam"
        risk_level = "High"
    
    # Grandparent Scams
    elif any(kw in transcript_lower for kw in grandparent_keywords):
        red_flags.append("Family Emergency Appeal")
        fraud_category = "Grandparent Scam"
        risk_level = "Critical"
    
    # Extortion/Blackmail
    elif any(kw in transcript_lower for kw in extortion_keywords):
        red_flags.append("Threats/Extortion")
        fraud_category = "Extortion/Blackmail"
        risk_level = "Critical"
    
    # Account Takeover
    elif any(kw in transcript_lower for kw in account_keywords):
        red_flags.append("Account Verification Request")
        fraud_category = "Account Takeover"
        risk_level = "High"
    
    # Social Media Scams
    elif any(kw in transcript_lower for kw in social_keywords):
        red_flags.append("Social Media Claim")
        fraud_category = "Social Media Scam"
        risk_level = "Medium"
    
    # Tax Scams
    elif any(kw in transcript_lower for kw in tax_keywords):
        red_flags.append("Tax/Refund Claim")
        fraud_category = "Tax Scam"
        risk_level = "High"
    
    # Utility Scams
    elif any(kw in transcript_lower for kw in utility_keywords):
        red_flags.append("Utility Service Threat")
        fraud_category = "Utility Scam"
        risk_level = "High"
    
    # Vehicle Scams
    elif any(kw in transcript_lower for kw in vehicle_keywords):
        red_flags.append("Vehicle/Accident Claim")
        fraud_category = "Vehicle Scam"
        risk_level = "Medium"
    
    # Add acoustic detection
    if acoustic_prediction == "AI VOICE CLONE" and risk_level == "Low":
        risk_level = "High"
        red_flags.insert(0, "Synthetic Voice Detected")
    elif acoustic_prediction == "VOICE CHANGER":
        risk_level = "High" if risk_level == "Low" else risk_level
        red_flags.insert(0, "Voice Modification Detected")
    
    combined_risk = anomaly_score * 0.6 + (min(len(red_flags), 3) * 0.15)
    combined_risk = min(combined_risk, 1.0)
    
    return {
        "semantic_available": False,
        "risk_level": risk_level,
        "scam_indicators": red_flags if red_flags else ["None detected"],
        "fraud_category": fraud_category,
        "explanation": f"Detected {len(red_flags)} fraud indicators" if red_flags else "No obvious fraud patterns detected.",
        "combined_risk_score": combined_risk
    }


def save_base64_audio_to_temp(filename: str, audio_b64: str) -> str:
    suffix = os.path.splitext(filename)[1].lower() or ".wav"
    if suffix != ".wav":
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="neurosync_", mode="wb") as tmp_file:
        tmp_file.write(base64.b64decode(audio_b64))
        return tmp_file.name


def extract_audio_features_from_waveform(y: np.ndarray, sr: int) -> torch.Tensor:
    if y.size == 0 or sr <= 0:
        raise ValueError("Empty or invalid waveform segment")

    hop_length = max(1, int(0.0125 * sr))
    n_fft = max(256, int(0.025 * sr))
    n_mfcc = 20

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length)
    if mfcc.shape[1] == 0:
        raise ValueError("MFCC extraction returned no frames")

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
    if feature_vector.shape[0] != EXPECTED_FEATURE_DIM:
        if feature_vector.shape[0] < EXPECTED_FEATURE_DIM:
            padding = np.zeros(EXPECTED_FEATURE_DIM - feature_vector.shape[0], dtype=np.float32)
            feature_vector = np.concatenate([feature_vector, padding], axis=0)
        else:
            feature_vector = feature_vector[:EXPECTED_FEATURE_DIM]

    return torch.from_numpy(feature_vector)


def extract_audio_features(audio_path: str) -> torch.Tensor:
    y, sr = librosa.load(audio_path, sr=TARGET_SR, mono=True)
    return extract_audio_features_from_waveform(y, sr)


def sliding_window_features(audio_path: str) -> list[tuple[float, float, torch.Tensor]]:
    y, sr = librosa.load(audio_path, sr=TARGET_SR, mono=True)
    if y.size == 0 or sr <= 0:
        raise ValueError(f"Empty or invalid waveform from {audio_path}")

    window_length = int(WINDOW_LENGTH_SECONDS * sr)
    hop_length = int(WINDOW_HOP_SECONDS * sr)

    if window_length <= 0 or hop_length <= 0:
        raise ValueError("Invalid sliding window configuration")

    feature_windows: list[tuple[float, float, torch.Tensor]] = []
    total_samples = y.shape[0]
    total_seconds = total_samples / float(sr)

    if total_samples < window_length:
        fv = extract_audio_features_from_waveform(y, sr)
        feature_windows.append((0.0, total_seconds, fv))
        return feature_windows

    for start_sample in range(0, total_samples - window_length + 1, hop_length):
        end_sample = start_sample + window_length
        segment = y[start_sample:end_sample]
        if segment.size == 0:
            continue
        start_s = float(start_sample) / float(sr)
        end_s = float(end_sample) / float(sr)
        fv = extract_audio_features_from_waveform(segment, sr)
        feature_windows.append((start_s, end_s, fv))

    if not feature_windows:
        raise ValueError("No valid sliding windows could be extracted from audio")

    return feature_windows


def map_class_label_to_prediction(label: str) -> str:
    normalized = str(label or "").strip().lower()
    if normalized in {"real", "safe"}:
        return "SAFE"
    if normalized in {"fake", "deepfake", "ai voice clone", "clone", "synthetic"}:
        return "AI VOICE CLONE"
    if normalized in {"mixed", "mixed real-ai", "mixed audio"}:
        return "UNKNOWN"
    if normalized == "voice changer":
        return "VOICE CHANGER"
    if normalized == "fraud":
        return "FRAUD"
    return normalized.upper() if normalized else "UNKNOWN"


def compute_deepfake_probability(audio_path: str) -> dict:
    if not MODEL_LOADED:
        raise RuntimeError("Model checkpoint is missing or failed to load. Acoustic classification is unavailable.")

    feature_tensor = extract_audio_features(audio_path)
    if feature_tensor.ndim != 1:
        feature_tensor = feature_tensor.view(-1)

    with torch.no_grad():
        logits = MODEL(feature_tensor.to(DEVICE).unsqueeze(0))
        if MODEL_CLASS_LABELS is not None and len(MODEL_CLASS_LABELS) > 1:
            probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy().tolist()
            scores = {label: float(score) for label, score in zip(MODEL_CLASS_LABELS, probs)}
            predicted_label = max(scores, key=scores.get)
            confidence = max(scores.values())
            anomaly_score = float(max(0.0, min(1.0, max(scores.get("fake", 0.0), scores.get("mixed", 0.0), 1.0 - scores.get("real", 0.0)))))
        else:
            prob = float(torch.sigmoid(logits).squeeze(1).cpu().item())
            prob = float(max(0.0, min(1.0, prob)))
            scores = {"real": 1.0 - prob, "fake": prob}
            predicted_label = "fake" if prob >= 0.5 else "real"
            confidence = max(scores.values())
            anomaly_score = prob

    overall_prediction = map_class_label_to_prediction(predicted_label)
    return {
        "summary": {
            "predicted_label": predicted_label,
            "prediction": overall_prediction,
            "class_scores": scores,
            "confidence": confidence,
            "anomaly_score": anomaly_score,
        },
        "segments": [
            {
                "start_s": 0.0,
                "end_s": float(librosa.get_duration(path=audio_path)),
                "duration_s": float(librosa.get_duration(path=audio_path)),
                "predicted_label": predicted_label,
                "prediction": overall_prediction,
                "class_scores": scores,
                "confidence": confidence,
                "anomaly_score": anomaly_score,
            }
        ],
        "top_suspicious_segments": [
            {
                "start_s": 0.0,
                "end_s": float(librosa.get_duration(path=audio_path)),
                "duration_s": float(librosa.get_duration(path=audio_path)),
                "predicted_label": predicted_label,
                "prediction": overall_prediction,
                "class_scores": scores,
                "confidence": confidence,
                "anomaly_score": anomaly_score,
            }
        ],
    }


def categorize_prediction(anomaly_score: float, predicted_label: str | None = None) -> str:
    if predicted_label:
        normalized = str(predicted_label).strip().lower()
        if normalized in {"real", "safe"}:
            return "SAFE"
        if normalized in {"fake", "deepfake", "ai voice clone", "clone", "synthetic"}:
            return "AI VOICE CLONE"
        if normalized in {"mixed", "mixed real-ai", "mixed audio"}:
            return "UNKNOWN"

    if anomaly_score < 0.5:
        return "SAFE"
    return "AI VOICE CLONE"


def build_analysis_payload(filename: str, prediction: str, confidence: float, anomaly_score: float, duration_s: float, processing_ms: int, audio_path: str = None):
    semantic_result = classify_audio_semantic(anomaly_score, prediction)
    
    # Always perform semantic analysis (Gemini or heuristic)
    transcript = ""
    semantic_analysis = None
    
    try:
        if audio_path and os.path.exists(audio_path):
            transcript = transcribe_audio_with_whisper(audio_path)
        else:
            transcript = "[No audio path provided for transcription]"
        
        # This will use Gemini if API key available, otherwise heuristic
        semantic_analysis = analyze_with_gemini(transcript, prediction, anomaly_score)
    except Exception as e:
        print(f"⚠️ Semantic analysis error: {e}")
        # Fallback to heuristic if anything fails
        semantic_analysis = get_semantic_analysis_heuristic(transcript, prediction, anomaly_score)
    
    # Merge acoustic and semantic results into explanation
    combined_explanation = semantic_result.get("action", "")
    if semantic_analysis:
        indicators = semantic_analysis.get("scam_indicators", [])
        fraud_cat = semantic_analysis.get("fraud_category", "None")
        if indicators and indicators != ["None detected"] and fraud_cat != "None":
            combined_explanation = f"{combined_explanation} | Fraud Detection: {fraud_cat} - {', '.join(indicators)}"
    
    return {
        "id": str(uuid4()),
        "filename": filename,
        "prediction": prediction,
        "confidence": round(confidence * 100.0, 2),
        "anomaly_score": round(anomaly_score, 4),
        "verdict": semantic_result["verdict"],
        "category": semantic_result["category"],
        "explanation": combined_explanation,
        "processing_ms": processing_ms,
        "duration_s": round(duration_s, 2),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "semantic_analysis": semantic_analysis,
        "transcript": transcript if transcript else None,
    }


def classify_audio_semantic(anomaly: float, prediction: str | None = None, semantic_risk: float = 0.0):
    if prediction and prediction != "SAFE":
        return {
            "category": "AI Voice Clone / Deepfake Replica",
            "verdict": "CRITICAL SECURITY MISMATCH",
            "action": "ALERT: Synthetic voice clone footprint identified by trained network weights!",
            "anomaly_score": round(anomaly, 4),
            "semantic_risk": round(semantic_risk, 4),
        }

    if anomaly >= 0.55:
        return {
            "category": "AI Voice Clone / Deepfake Replica",
            "verdict": "CRITICAL SECURITY MISMATCH",
            "action": "ALERT: Synthetic voice clone footprint identified by trained network weights!",
            "anomaly_score": round(anomaly, 4),
            "semantic_risk": round(semantic_risk, 4),
        }

    return {
        "category": "Verified Clean User",
        "verdict": "VERIFIED SAFE",
        "action": "ALLOW AUDIO ROUTE STREAM: Audio wave structures match biological vocal tracts.",
        "anomaly_score": round(anomaly, 4),
        "semantic_risk": round(semantic_risk, 4),
    }


@app.route("/analyze", methods=["POST"])
def analyze():
    temp_audio_path = None
    try:
        if request.files and "audio" in request.files:
            uploaded_file = request.files["audio"]
            filename = uploaded_file.filename or "upload.wav"
            suffix = os.path.splitext(filename)[1].lower() or ".wav"
            if suffix != ".wav":
                return jsonify({"error": "Only .wav audio files are supported."}), 400

            temp_audio_path = os.path.join(tempfile.gettempdir(), f"neurosync_upload{suffix}")
            uploaded_file.save(temp_audio_path)
            audio_path = temp_audio_path
        else:
            payload = request.get_json(silent=True) or {}
            audio_b64 = payload.get("audio_b64", "")
            filename = payload.get("filename", "upload.wav")

            if not isinstance(audio_b64, str) or not audio_b64.strip():
                return jsonify({"error": "audio file upload or audio_b64 is required."}), 400

            temp_audio_path = save_base64_audio_to_temp(filename, audio_b64)
            audio_path = temp_audio_path

        analysis = compute_deepfake_probability(audio_path)
        anomaly_score = analysis["summary"]["anomaly_score"]
        prediction = analysis["summary"].get("prediction", "SAFE")
        semantic_result = classify_audio_semantic(anomaly_score, prediction)
        
        # Always perform semantic analysis (Gemini or heuristic)
        transcript = ""
        semantic_analysis = None
        try:
            transcript = transcribe_audio_with_whisper(audio_path)
            # This will use Gemini if API key available, otherwise heuristic
            semantic_analysis = analyze_with_gemini(transcript, prediction, anomaly_score)
        except Exception as e:
            print(f"⚠️ Semantic analysis error: {e}")
            # Fallback to heuristic
            semantic_analysis = get_semantic_analysis_heuristic(transcript, prediction, anomaly_score)

        return jsonify({
            "anomaly_score": semantic_result["anomaly_score"],
            "semantic_risk": semantic_result["semantic_risk"],
            "category": semantic_result["category"],
            "verdict": semantic_result["verdict"],
            "action": semantic_result["action"],
            "analysis": analysis,
            "transcript": transcript if transcript else None,
            "semantic_analysis": semantic_analysis,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass


@app.route("/api/upload", methods=["POST"])
def upload_audio():
    if not MODEL_LOADED:
        return jsonify({"error": "Model checkpoint unavailable. Please start the backend after placing the checkpoint."}), 503

    temp_audio_path = None
    try:
        if request.files and "audio" in request.files:
            uploaded_file = request.files["audio"]
            filename = uploaded_file.filename or "upload.wav"
            suffix = os.path.splitext(filename)[1].lower() or ".wav"
            if suffix not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
                suffix = ".wav"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="neurosync_upload_") as tmp_file:
                uploaded_file.save(tmp_file.name)
                temp_audio_path = tmp_file.name
            audio_path = temp_audio_path
        else:
            payload = request.get_json(silent=True) or {}
            audio_b64 = payload.get("audio_b64", "")
            filename = payload.get("filename", "upload.wav")

            if not isinstance(audio_b64, str) or not audio_b64.strip():
                return jsonify({"error": "audio file upload or audio_b64 is required."}), 400

            temp_audio_path = save_base64_audio_to_temp(filename, audio_b64)
            audio_path = temp_audio_path

        start_time = datetime.utcnow()
        analysis = compute_deepfake_probability(audio_path)
        anomaly_score = analysis["summary"]["anomaly_score"]
        prediction = analysis["summary"].get("prediction", "SAFE")
        confidence = analysis["summary"].get("confidence", 0.0)
        duration_s = float(librosa.get_duration(path=audio_path))
        processing_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result = build_analysis_payload(filename, prediction, confidence, anomaly_score, duration_s, processing_ms, audio_path=audio_path)
        append_history(result)

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass


@app.route("/api/history", methods=["GET"])
def history():
    history_data = load_history()
    return jsonify({"history": history_data})


@app.route("/api/profile", methods=["GET"])
def profile():
    return jsonify({
        "name": "Arjun Mehta",
        "phone": "+91 98765 43210",
        "email": "arjun.mehta@neurosync.io",
        "organization": "NeuroSync Labs",
        "joined": "April 2025",
        "bio": "Security analyst using NeuroSync Guard to detect synthetic and manipulated voice calls.",
    })


@app.route("/api/about", methods=["GET"])
def about():
    return jsonify({
        "title": "NeuroSync Guard",
        "description": "A lightweight voice authentication and anti-fraud monitor for call audio. The system analyzes acoustic fingerprint features and a trained deepfake detector to identify suspicious synthetic vocal signals.",
        "privacy_policy": "All uploaded audio is processed only for analysis. Only anonymized metadata is persisted in the local history log. Raw recordings are not shared externally.",
        "privacy_bullets": [
            "Audio is analyzed locally and never transmitted to third-party services.",
            "Only anonymized scan metadata is kept in the local history file.",
            "The model returns a prediction score and confidence for each recording.",
            "Uploads are retained for audit and review but not used to retrain the model automatically.",
        ],
    })


if __name__ == "__main__":
    print(f"🚀 NeuroSync-Guard Flask backend listening on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
