import React, { useState, useEffect, useRef } from "react";
import {
  Shield, Phone, Upload, Bell, History as HistoryIcon, Settings, User,
  Globe, LogOut, ChevronRight, Search, ArrowLeft, CheckCircle2,
  AlertTriangle, Menu, X, Home, Lock, FileText, HelpCircle, Info,
  Moon, Sun, ShieldAlert, ShieldCheck, ChevronDown, Mic, Grid, Volume2,
  Video, PhoneCall
} from "lucide-react";

/* ---------------------------------------------------------
   DATA
--------------------------------------------------------- */

const PALETTE = {
  blue: "#2563EB",
  blueDark: "#1E3A8A",
  bg: "#F5F7FB",
};

// Styles applied to the inner phone screen container
const filterStyle = {
  background: "white",
};

const detectionStyles = {
  SAFE:          { color: "#16A34A", bg: "#DCFCE7" },
  "AI VOICE CLONE": { color: "#DC2626", bg: "#FEE2E2" },
  "VOICE CHANGER": { color: "#7E22CE", bg: "#F3E8FF" },
  FRAUD:         { color: "#EA580C", bg: "#FFEDD5" },
  UNKNOWN:       { color: "#2563EB", bg: "#DBEAFE" },
};

const predictionLabels = {
  SAFE: "Safe",
  "AI VOICE CLONE": "AI VOICE CLONE",
  "VOICE CHANGER": "Voice Changer",
  FRAUD: "FRAUD",
  UNKNOWN: "UNKNOWN",
};

const API_BASE_URL = "http://localhost:5001";

const summaries = {
  SAFE: "No AI manipulation detected.",
  "AI VOICE CLONE": "Voice cloning characteristics detected.",
  "VOICE CHANGER": "Real-time voice changer detected.",
  FRAUD: "Potential fraud indicators found.",
  UNKNOWN: "Inconclusive audio analysis. Try a cleaner recording.",
};

function getSemanticSummary(semanticAnalysis) {
  if (!semanticAnalysis) return "";
  const indicators = semanticAnalysis.scam_indicators || [];
  const category = semanticAnalysis.fraud_category || "None";
  if (indicators.length === 0 || indicators[0] === "None detected") {
    return "No fraud patterns detected in transcript.";
  }
  return `Fraud indicators: ${indicators.join(", ")}. Category: ${category}.`;
}

const resultCases = {
  "VOICE CHANGER": {
    title: "VOICE CHANGER DETECTED",
    message: "The opposite person appears to be using a real-time voice changer application. Their original voice has been digitally modified. Proceed with caution.",
    risk: "High", confidence: "98%", icon: "shield-alert",
    primary: "Back to Dashboard", secondary: "View Full Report",
  },
  "AI VOICE CLONE": {
    title: "AI-GENERATED VOICE DETECTED",
    message: "The recording appears to be synthetic or cloned. The voice characteristics match AI-generated speech patterns, so the source should be treated as unverified.",
    risk: "Critical", confidence: "99%", icon: "shield-alert",
    primary: "Back to Dashboard", secondary: "View Report",
  },
  FRAUD: {
    title: "POTENTIAL FRAUD DETECTED",
    message: "Multiple indicators associated with scam or fraudulent calls have been detected. Avoid sharing OTPs, passwords, banking details, or personal information.",
    risk: "Critical", confidence: "97%", icon: "shield-alert",
    primary: "Block Number", secondary: "Back to Dashboard",
  },
  SAFE: {
    title: "REAL HUMAN VOICE DETECTED",
    message: "No AI-generated voice detected. The recording appears to be a genuine human voice with no synthetic or cloned characteristics.",
    risk: "Low", confidence: "96%", icon: "shield-check",
    primary: "Back to Dashboard", secondary: null,
  },
  UNKNOWN: {
    title: "UNKNOWN RESULT",
    message: "The classifier returned an inconclusive score. Review the upload and retry with a clean sample for a clearer verdict.",
    risk: "Moderate", confidence: "--", icon: "shield-alert",
    primary: "Back to Dashboard", secondary: null,
  },
};

function normalizePrediction(value) {
  if (!value || typeof value !== "string") return "UNKNOWN";
  const normalized = value.trim().toUpperCase();
  if (normalized === "SAFE") return "SAFE";
  if (normalized === "AI VOICE CLONE") return "AI VOICE CLONE";
  if (normalized === "VOICE CHANGER") return "VOICE CHANGER";
  if (normalized === "FRAUD") return "FRAUD";
  if (normalized === "UNKNOWN") return "UNKNOWN";
  return "UNKNOWN";
}

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

const languages = ["English", "Hindi", "Telugu", "Tamil", "Kannada", "Malayalam"];

const MOCK_FAKE_CALL = {
  callerName: "Johony Doe",
  number: "12 34 5678",
  audioSrc: "/sos.wav",
};

const MOCK_RECENT_CALLS = [
  {
    id: "call-1",
    num: "+91 98765 43210",
    time: "Today, 09:12 AM",
    confidence: 92,
    type: "SAFE",
    duration: "00:28",
  },
  {
    id: "call-2",
    num: "+91 91234 56780",
    time: "Yesterday, 05:34 PM",
    confidence: 76,
    type: "AI VOICE CLONE",
    duration: "00:15",
  },
  {
    id: "call-3",
    num: "+91 99887 66554",
    time: "Yesterday, 11:07 AM",
    confidence: 82,
    type: "VOICE CHANGER",
    duration: "00:42",
  },
  {
    id: "call-4",
    num: "+91 90123 45678",
    time: "Mon, 08:10 AM",
    confidence: 88,
    type: "SAFE",
    duration: "00:19",
  },
  {
    id: "call-5",
    num: "+91 97012 34567",
    time: "Sun, 09:55 PM",
    confidence: 79,
    type: "FRAUD",
    duration: "00:33",
  },
];

const MOCK_HISTORY_DATA = [
  {
    id: "history-1",
    filename: "sos.wav",
    created_at: new Date().toISOString(),
    confidence: 92,
    prediction: "SAFE",
  },
  {
    id: "history-2",
    filename: "call_recording.wav",
    created_at: new Date(Date.now() - 3600 * 1000 * 24).toISOString(),
    confidence: 76,
    prediction: "AI VOICE CLONE",
  },
  {
    id: "history-3",
    filename: "important_call.wav",
    created_at: new Date(Date.now() - 3600 * 1000 * 26).toISOString(),
    confidence: 82,
    prediction: "VOICE CHANGER",
  },
];

const MOCK_PROFILE = {
  name: "Arjun Mehta",
  phone: "+91 98765 43210",
  email: "arjun.mehta@neurosync.io",
  organization: "NeuroSync Labs",
  joined: "April 2025",
  bio: "Security analyst using NeuroSync Guard to detect synthetic and manipulated voice calls.",
};

const MOCK_ABOUT_INFO = {
  title: "NeuroSync Guard",
  description: "A lightweight voice authentication and anti-fraud monitor for call audio. The system analyzes acoustic fingerprint features and a trained deepfake detector to identify suspicious synthetic vocal signals.",
  privacy_policy: "All uploaded audio is processed only for analysis. Only anonymized metadata is persisted in the local history log. Raw recordings are not shared externally.",
  privacy_bullets: [
    "Audio is analyzed locally and never transmitted to third-party services.",
    "Only anonymized scan metadata is kept in the local history file.",
    "The model returns a prediction score and confidence for each recording.",
    "Uploads are retained for audit and review but not used to retrain the model automatically.",
  ],
};

/* ---------------------------------------------------------
   SMALL SHARED COMPONENTS
--------------------------------------------------------- */

function Switch({ on, onClick, size = "md" }) {
  const dims = size === "sm"
    ? { w: 40, h: 22, knob: 18 }
    : { w: 48, h: 28, knob: 24 };
  return (
    <button
      onClick={onClick}
      className="relative shrink-0 rounded-full transition-colors duration-200"
      style={{ width: dims.w, height: dims.h, background: on ? PALETTE.blue : "#CBD5E1" }}
    >
      <span
        className="absolute top-0.5 rounded-full bg-white transition-transform duration-200"
        style={{
          width: dims.knob, height: dims.knob,
          left: 2,
          transform: on ? `translateX(${dims.w - dims.knob - 4}px)` : "translateX(0px)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
        }}
      />
    </button>
  );
}

function Badge({ type }) {
  const normalizedType = normalizePrediction(type);
  const d = detectionStyles[normalizedType] || detectionStyles.UNKNOWN;
  return (
    <span
      className="text-[10px] font-bold px-2.5 py-1 rounded-full shrink-0"
      style={{ color: d.color, background: d.bg }}
    >
      {normalizedType === "UNKNOWN" ? "Unknown" : type}
    </span>
  );
}

function CallCard({ call, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl px-4 py-3.5 bg-white flex items-center justify-between active:scale-[0.98] transition-transform duration-150"
      style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="rounded-full flex items-center justify-center shrink-0" style={{ width: 40, height: 40, background: "#EEF2FF" }}>
          <Phone size={16} color={PALETTE.blue} />
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-bold text-slate-900 truncate">{call.num}</div>
          <div className="text-[10.5px] text-slate-400 mt-0.5">{call.time} · {call.confidence ?? "--"}% confidence</div>
        </div>
      </div>
      <Badge type={call.type} />
    </button>
  );
}

function TopBar({ onMenu, title = "NeuroSync Guard" }) {
  return (
    <div className="flex items-center justify-between px-4 pt-3 pb-2">
      <button onClick={onMenu} className="rounded-full flex items-center justify-center active:scale-95 transition-transform" style={{ width: 36, height: 36, background: "#EEF2FF" }}>
        <Menu size={17} color={PALETTE.blueDark} />
      </button>
      <span className="text-[15px] font-bold text-slate-900">{title}</span>
      <button className="rounded-full flex items-center justify-center active:scale-95 transition-transform" style={{ width: 36, height: 36, background: "#EEF2FF" }}>
        <Bell size={16} color={PALETTE.blueDark} />
      </button>
    </div>
  );
}
 

function BackBar({ onBack, title }) {
  return (
    <div className="flex items-center gap-3 px-4 pt-4 pb-3">
      <button onClick={onBack} className="rounded-full flex items-center justify-center active:scale-95 transition-transform" style={{ width: 36, height: 36, background: "#EEF2FF" }}>
        <ArrowLeft size={16} color={PALETTE.blueDark} />
      </button>
      <span className="text-[15px] font-bold text-slate-900">{title}</span>
    </div>
  );
}

function SettingsRow({ icon, label, right, onClick, last }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-4 py-3.5 ${last ? "" : "border-b"} active:bg-slate-50 transition-colors`}
      style={{ borderColor: "#F1F5F9" }}
    >
      <span className="flex items-center gap-3 text-[13px] font-medium text-slate-900">
        {icon}
        {label}
      </span>
      {right}
    </button>
  );
}

/* ---------------------------------------------------------
   SCREENS
--------------------------------------------------------- */

function SplashScreen() {
  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center"
      style={{ background: `linear-gradient(160deg, #2563EB 0%, #1E3A8A 60%, #14245C 100%)` }}
    >
      <div className="rounded-3xl flex items-center justify-center mb-5" style={{ width: 84, height: 84, background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)" }}>
        <Shield size={38} color="white" />
      </div>
      <div className="text-white text-[21px] font-extrabold tracking-tight">NeuroSync Guard</div>
      <div className="text-white/70 text-[12px] mt-2 tracking-wide">Protecting Every Voice.</div>
    </div>
  );
}

function DashboardScreen({ onMenu, protectionOn, setProtectionOn, onOpenCall, recentCalls = [], onFakeCall }) {
  const displayRecentCalls = (recentCalls.length > 0 ? recentCalls : MOCK_RECENT_CALLS)
    .slice(0, 5)
    .map((call, index) => ({
      id: call.id || `recent-${index}`,
      num: call.num || call.phone || call.number || `+91 9${String(index + 8000000000).slice(-10)}`,
      time: call.time || (call.created_at ? new Date(call.created_at).toLocaleString() : "Recent call"),
      confidence: call.confidence ?? 88,
      type: normalizePrediction(call.prediction || call.type || "SAFE"),
      duration: call.duration || "00:20",
    }));

  return (
    <div className="h-full overflow-y-auto pb-24 relative" style={{ background: PALETTE.bg }}>
      <TopBar onMenu={onMenu} />

      <div className="px-4 pt-1 pb-3">
        <div className="text-[13px] text-slate-500">Good Morning,</div>
        <div className="text-[18px] font-bold text-slate-900">User</div>
      </div>

      <div className="px-4 mb-5">
        <div
          className="rounded-[20px] p-5 transition-colors duration-300"
          style={{
            background: protectionOn ? "linear-gradient(135deg, #2563EB, #1E3A8A)" : "#E9EDF3",
            boxShadow: "0 8px 24px -8px rgba(15,23,42,0.18)",
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-[13px] font-semibold" style={{ color: protectionOn ? "rgba(255,255,255,0.85)" : "#475569" }}>
              Protection Status
            </span>
            <Switch on={protectionOn} onClick={() => setProtectionOn(!protectionOn)} />
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-2xl flex items-center justify-center" style={{ width: 44, height: 44, background: protectionOn ? "rgba(255,255,255,0.18)" : "#DBE2EB" }}>
              <Shield size={20} color={protectionOn ? "white" : "#475569"} />
            </div>
            <div>
              <div className="text-[14px] font-bold" style={{ color: protectionOn ? "white" : "#475569" }}>
                {protectionOn ? "Live AI Call Protection Enabled" : "Protection Disabled"}
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: protectionOn ? "rgba(255,255,255,0.7)" : "#94A3B8" }}>
                {protectionOn ? "Incoming calls are monitored in real time." : "Enable Live Call Protection"}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between px-4 mb-2.5">
        <span className="text-[13px] font-bold text-slate-900">Recent Calls</span>
        <span className="text-[11px] font-medium" style={{ color: PALETTE.blue }}>View all</span>
      </div>

      <div className="px-4 space-y-2.5 pb-16">
        {displayRecentCalls.length > 0 ? displayRecentCalls.map((c) => (
          <CallCard key={c.id} call={c} onClick={() => onOpenCall(c)} />
        )) : (
          <div className="rounded-2xl px-4 py-6 bg-white text-center text-[12px] text-slate-500" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            No recent calls available. Upload an audio recording to start detection.
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryScreen({ historyData }) {
  const [filter, setFilter] = useState("All");
  const chips = ["All", "Safe", "AI VOICE CLONE", "Voice Changer", "FRAUD", "Unknown"];
  const normalizedFilter = filter === "All" ? null : normalizePrediction(filter);
  const filtered = normalizedFilter ? historyData.filter((c) => normalizePrediction(c.prediction) === normalizedFilter) : historyData;

  return (
    <div className="h-full overflow-y-auto pb-24" style={{ background: PALETTE.bg }}>
      <div className="px-4 pt-4 pb-3">
        <span className="text-[16px] font-bold text-slate-900">History</span>
      </div>

      <div className="px-4 mb-3">
        <div className="rounded-xl px-3.5 py-2.5 flex items-center gap-2" style={{ background: "#EEF1F6" }}>
          <Search size={14} color="#94A3B8" />
          <span className="text-[12px] text-slate-400">Search recordings</span>
        </div>
      </div>

      <div className="px-4 mb-3 flex gap-2 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
        {chips.map((chip) => (
          <button
            key={chip}
            onClick={() => setFilter(chip)}
            className="px-3.5 py-1.5 rounded-full text-[11.5px] font-semibold whitespace-nowrap transition-colors"
            style={{
              background: filter === chip ? PALETTE.blue : "white",
              color: filter === chip ? "white" : "#475569",
              border: filter === chip ? "none" : "1px solid #E2E8F0",
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      <div className="px-4 space-y-2.5">
        {filtered.length > 0 ? filtered.map((c) => (
          <div key={c.id} className="rounded-2xl px-4 py-3.5 bg-white flex items-center justify-between" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            <div className="flex items-center gap-3 min-w-0">
              <div className="rounded-full flex items-center justify-center shrink-0" style={{ width: 40, height: 40, background: "#EEF2FF" }}>
                <Phone size={16} color={PALETTE.blue} />
              </div>
              <div className="min-w-0">
                <div className="text-[13px] font-bold text-slate-900 truncate">{c.filename}</div>
                <div className="text-[10.5px] text-slate-400 mt-0.5">{new Date(c.created_at).toLocaleString()} · {c.confidence}%</div>
              </div>
            </div>
            <Badge type={c.prediction} />
          </div>
        )) : (
          <div className="text-center text-[12px] text-slate-400 pt-10">No recordings found for this filter.</div>
        )}
      </div>
    </div>
  );
}

function AlertsScreen({ historyData }) {
  const alerts = historyData
    .filter((entry) => ["AI VOICE CLONE", "VOICE CHANGER", "FRAUD"].includes(entry.prediction))
    .slice(0, 6)
    .map((entry) => ({
      id: entry.id,
      title: `${entry.prediction} Detected`,
      sub: `${entry.filename} · ${new Date(entry.created_at).toLocaleString()}`,
      type: normalizePrediction(entry.prediction),
    }));

  return (
    <div className="h-full overflow-y-auto pb-24" style={{ background: PALETTE.bg }}>
      <div className="px-4 pt-4 pb-3">
        <span className="text-[16px] font-bold text-slate-900">Alerts</span>
      </div>
      <div className="px-4 space-y-2.5">
        {alerts.length > 0 ? alerts.map((a) => {
          const d = detectionStyles[a.type] || detectionStyles.UNKNOWN;
          return (
            <div key={a.id} className="rounded-2xl px-4 py-3.5 bg-white flex items-center gap-3" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
              <div className="rounded-full flex items-center justify-center shrink-0" style={{ width: 40, height: 40, background: d.bg }}>
                <AlertTriangle size={16} color={d.color} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-bold text-slate-900 truncate">{a.title}</div>
                <div className="text-[10.5px] text-slate-400 mt-0.5">{a.sub}</div>
              </div>
              <span className="rounded-full shrink-0" style={{ width: 8, height: 8, background: d.color }} />
            </div>
          );
        }) : (
          <div className="rounded-2xl px-4 py-6 bg-white text-center text-[12px] text-slate-500" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            No alert-level findings yet. Upload a recording to build your alert history.
          </div>
        )}
      </div>
    </div>
  );
}

function CallDetailsScreen({ call, onBack }) {
  if (!call) return null;
  const prediction = normalizePrediction(call.prediction || call.type || "UNKNOWN");
  const risk = prediction === "SAFE" ? "Low" : prediction === "FRAUD" || prediction === "AI VOICE CLONE" ? "Critical" : "High";
  const bars = Array.from({ length: 46 }, (_, i) => 8 + Math.round(18 * Math.abs(Math.sin(i * 0.7))));

  return (
    <div className="h-full overflow-y-auto" style={{ background: PALETTE.bg }}>
      <BackBar onBack={onBack} title="Call Details" />
      <div className="px-4 pb-8">
        <div className="rounded-[20px] p-5 bg-white text-center mb-4" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="text-[18px] font-bold text-slate-900">{call.num}</div>
          <div className="flex justify-center gap-4 mt-3 text-[11.5px] text-slate-500">
            <span>Duration: {call.duration}</span>
            <span>{call.date}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="rounded-2xl p-4 bg-white" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            <div className="text-[11px] text-slate-500">Risk Score</div>
            <div className="text-[18px] font-bold mt-1 text-slate-900">{risk}</div>
          </div>
          <div className="rounded-2xl p-4 bg-white" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            <div className="text-[11px] text-slate-500">Confidence</div>
            <div className="text-[18px] font-bold mt-1 text-slate-900">{call.confidence}%</div>
          </div>
        </div>

        <div className="rounded-2xl p-4 bg-white mb-4" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="text-[11px] text-slate-500 mb-2">Prediction</div>
          <Badge type={prediction} />
        </div>

        <div className="rounded-2xl p-4 bg-white mb-4" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="text-[11px] text-slate-500 mb-2">Waveform</div>
          <div className="flex items-end gap-[3px]" style={{ height: 44 }}>
            {bars.map((h, i) => (
              <div key={i} style={{ width: 3, height: h, background: PALETTE.blue, opacity: 0.75, borderRadius: 2 }} />
            ))}
          </div>
        </div>

        <div className="rounded-2xl p-4 bg-white" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="text-[11px] text-slate-500 mb-1.5">Analysis Summary</div>
          <div className="text-[12.5px] leading-relaxed text-slate-900">{summaries[prediction] || summaries[call.type] || "Detailed acoustic analysis has been logged."}</div>
        </div>
      </div>
    </div>
  );
}

function UploadScreen({ onBack, onResult, refreshHistory }) {
  const [stage, setStage] = useState("idle"); // idle | uploading | analyzing
  const [fileName, setFileName] = useState(null);
  const [error, setError] = useState(null);

  async function startUpload(file) {
    setError(null);
    if (!file) return;

    setFileName(file.name);
    setStage("uploading");

    try {
      const formData = new FormData();
      formData.append("audio", file, file.name || "upload.wav");

      setStage("analyzing");
      const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Upload failed.");
      }

      refreshHistory();
      onResult(payload);
    } catch (err) {
      setError(err.message || "Unable to process audio.");
      setStage("idle");
    }
  }

  return (
    <div className="h-full overflow-y-auto relative" style={{ background: PALETTE.bg }}>
      <BackBar onBack={onBack} title="Upload Recording" />
      <div className="px-4 pb-8">
        <p className="text-[12.5px] text-slate-500 mb-5">
          Upload an audio recording to detect AI-generated voices.
        </p>

        <label className="block rounded-[22px] p-8 text-center mb-5 cursor-pointer" style={{ border: "2px dashed #C7D2FE", background: "#F5F7FF" }}>
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.aac,.flac,.ogg"
            className="hidden"
            onChange={(e) => e.target.files[0] && startUpload(e.target.files[0])}
          />
          <div className="flex justify-center mb-3">
            <Upload size={30} color={PALETTE.blue} />
          </div>
          <div className="text-[14px] font-bold text-slate-900">Drag &amp; drop your recording</div>
          <div className="text-[11px] mt-1.5 text-slate-500">Supports MP3 · WAV · M4A · AAC · FLAC · OGG</div>
        </label>

        <button
          onClick={() => document.querySelector('#recording-input')?.click()}
          className="w-full py-3.5 rounded-2xl text-[13.5px] font-bold text-white active:scale-[0.98] transition-transform"
          style={{ background: PALETTE.blue }}
        >
          Choose Recording
        </button>
        <input id="recording-input" type="file" accept=".mp3,.wav,.m4a,.aac,.flac,.ogg" className="hidden" onChange={(e) => e.target.files[0] && startUpload(e.target.files[0])} />

        {fileName && stage === "idle" && (
          <div className="mt-4 rounded-xl px-3.5 py-3 flex items-center justify-between" style={{ background: "#F5F7FF" }}>
            <span className="text-[11.5px] text-slate-800 truncate">🎵 {fileName}</span>
            <span className="text-[10px] text-slate-400">Ready for upload</span>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl px-3.5 py-3 text-[12px] text-red-700 bg-red-100">
            {error}
          </div>
        )}
      </div>

      {stage !== "idle" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white">
          <div
            className="rounded-full animate-spin mb-5"
            style={{ width: 46, height: 46, border: "4px solid #E6E9F2", borderTopColor: PALETTE.blue }}
          />
          <div className="text-[14px] font-bold text-slate-900">
            {stage === "uploading" ? "Uploading..." : "Analyzing Audio..."}
          </div>
          <div className="text-[11px] mt-1.5 text-slate-500">Please keep the app open</div>
        </div>
      )}
    </div>
  );
}

function AboutScreen({ onBack, aboutInfo, aboutMode }) {
  if (!aboutInfo) return null;
  const showPrivacyOnly = aboutMode === "privacy";

  return (
    <div className="h-full overflow-y-auto" style={{ background: PALETTE.bg }}>
      <BackBar onBack={onBack} title={showPrivacyOnly ? "Privacy Policy" : "About"} />
      <div className="px-4 pb-8 space-y-4">
        {!showPrivacyOnly && (
          <div className="rounded-[20px] p-5 bg-white" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
            <div className="text-[15px] font-bold text-slate-900 mb-2">{aboutInfo.title}</div>
            <div className="text-[12.5px] text-slate-600 leading-relaxed">{aboutInfo.description}</div>
          </div>
        )}

        <div className="rounded-[20px] p-5 bg-white" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="text-[13px] font-semibold text-slate-900 mb-3">Privacy policy</div>
          <div className="text-[12.5px] text-slate-600 leading-relaxed mb-3">{aboutInfo.privacy_policy}</div>
          <div className="space-y-2 text-[12.5px] text-slate-600">
            {aboutInfo.privacy_bullets.map((item, index) => (
              <div key={index} className="flex gap-2">
                <span className="text-slate-400">•</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ResultScreen({ result, onBack }) {
  const caseKey = normalizePrediction(result?.prediction || result?.type || "UNKNOWN");
  const r = resultCases[caseKey] || resultCases.UNKNOWN;
  const semanticAnalysis = result?.semantic_analysis;
  // Show semantic analysis if it exists and has fraud category (works with both Gemini and heuristic)
  const hasSemanticData = semanticAnalysis && (semanticAnalysis.fraud_category || semanticAnalysis.risk_level);
  
  return (
    <div
      className="absolute inset-0 flex flex-col overflow-y-auto"
      style={{ background: "linear-gradient(160deg, #2563EB 0%, #1E3A8A 60%, #14245C 100%)" }}
    >
      <div className="flex flex-col items-center px-7 pt-8 pb-4">
        <div className="mb-4">
          {r.icon === "shield-check"
            ? <ShieldCheck size={56} color="#86EFAC" />
            : <ShieldAlert size={56} color="white" />}
        </div>
        <div className="text-white text-[19px] font-extrabold leading-relaxed mb-3">{r.title}</div>
        <div className="text-white/85 text-[13px] leading-relaxed mb-5">{r.message}</div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="rounded-2xl px-4 py-3 text-center" style={{ background: "rgba(255,255,255,0.14)" }}>
            <div className="text-[10px] text-white/60">Risk Level</div>
            <div className="text-[14px] font-bold text-white mt-0.5">{r.risk}</div>
          </div>
          <div className="rounded-2xl px-4 py-3 text-center" style={{ background: "rgba(255,255,255,0.14)" }}>
            <div className="text-[10px] text-white/60">Confidence</div>
            <div className="text-[14px] font-bold text-white mt-0.5">{result.confidence}%</div>
          </div>
        </div>

        <div className="rounded-2xl px-4 py-4 mb-4 bg-white/10 w-full" style={{ backdropFilter: "blur(8px)" }}>
          <div className="text-[11px] text-white/70 mb-2">Source</div>
          <div className="text-white text-[13px] font-semibold">{result.filename}</div>
          <div className="text-[11px] text-white/70 mt-1">Processed in {result.processing_ms} ms</div>
        </div>

        <div className="rounded-2xl px-4 py-4 mb-4 bg-white/10 w-full" style={{ backdropFilter: "blur(8px)" }}>
          <div className="text-[11px] text-white/70 mb-2">Acoustic Analysis</div>
          <div className="text-[13px] text-white/90">{result.explanation || summaries[caseKey]}</div>
          {result.anomaly_score !== undefined && (
            <div className="text-[10px] text-white/60 mt-2">Anomaly Score: {(result.anomaly_score * 100).toFixed(1)}%</div>
          )}
        </div>

        {hasSemanticData && (
          <>
            <div className="rounded-2xl px-4 py-4 mb-4 bg-white/10 w-full" style={{ backdropFilter: "blur(8px)" }}>
              <div className="text-[11px] text-white/70 mb-2">🔍 Semantic Analysis (Scam Detection)</div>
              <div className="text-[13px] text-white/90 mb-3">{semanticAnalysis.explanation}</div>
              <div className="space-y-2">
                <div><span className="text-[11px] text-white/70">Risk Level:</span> <span className="text-[12px] font-semibold text-white">{semanticAnalysis.risk_level}</span></div>
                <div><span className="text-[11px] text-white/70">Fraud Type:</span> <span className="text-[12px] font-semibold text-white">{semanticAnalysis.fraud_category}</span></div>
                {semanticAnalysis.scam_indicators && semanticAnalysis.scam_indicators.length > 0 && semanticAnalysis.scam_indicators[0] !== "None detected" && (
                  <div>
                    <span className="text-[11px] text-white/70 block mb-1">Red Flags:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {semanticAnalysis.scam_indicators.map((indicator, i) => (
                        <span key={i} className="text-[10px] px-2 py-1 rounded-full bg-white/20 text-white/90">{indicator}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="px-6 pb-9 mt-4">
        <button
          onClick={onBack}
          className="w-full py-3.5 rounded-2xl font-bold text-[13.5px] mb-2.5 active:scale-[0.98] transition-transform"
          style={{ background: "white", color: PALETTE.blueDark }}
        >
          {r.primary}
        </button>
        {r.secondary && (
          <button
            onClick={onBack}
            className="w-full py-3 rounded-2xl font-semibold text-[12.5px] text-white active:scale-[0.98] transition-transform"
            style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.3)" }}
          >
            {r.secondary}
          </button>
        )}
      </div>
    </div>
  );
}

function ProfileScreen({ profile, protectionOn, setProtectionOn, language, onOpenLanguage, darkMode, setDarkMode, onOpenAbout }) {
  const [notif, setNotif] = useState(true);
  return (
    <div className="h-full overflow-y-auto pb-24" style={{ background: PALETTE.bg }}>
      <div className="px-4 pt-4 pb-3">
        <span className="text-[16px] font-bold text-slate-900">Profile</span>
      </div>

      <div className="px-4 mb-5">
        <div className="rounded-[20px] p-5 bg-white flex items-center gap-3.5" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <div className="rounded-full flex items-center justify-center shrink-0" style={{ width: 64, height: 64, background: "#EEF2FF" }}>
            <User size={26} color={PALETTE.blue} />
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-bold text-slate-900">{profile?.name || "Security Analyst"}</div>
            <div className="text-[11.5px] mt-1 text-slate-500 flex items-center gap-1.5"><Phone size={11} /> {profile?.phone || "-"}</div>
            <div className="text-[11.5px] mt-0.5 text-slate-500 truncate">✉️ {profile?.email || "-"}</div>
          </div>
        </div>
      </div>

      <div className="px-4 mb-2.5">
        <span className="text-[12px] font-bold tracking-wide text-slate-500">SETTINGS</span>
      </div>

      <div className="px-4">
        <div className="rounded-[20px] bg-white overflow-hidden" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <SettingsRow
            icon={<Shield size={15} color={PALETTE.blueDark} />}
            label="Enable Live Protection"
            right={<Switch on={protectionOn} onClick={() => setProtectionOn(!protectionOn)} size="sm" />}
          />
          <SettingsRow
            icon={<Globe size={15} color={PALETTE.blueDark} />}
            label="Language"
            onClick={onOpenLanguage}
            right={<span className="text-[11.5px] text-slate-400 flex items-center gap-1">{language} <ChevronRight size={13} /></span>}
          />
          <SettingsRow
            icon={<Bell size={15} color={PALETTE.blueDark} />}
            label="Notifications"
            right={<Switch on={notif} onClick={() => setNotif(!notif)} size="sm" />}
          />
          <SettingsRow
            icon={<Moon size={15} color={PALETTE.blueDark} />}
            label="Dark Mode"
            right={<Switch on={darkMode} onClick={() => setDarkMode(!darkMode)} size="sm" />}
          />
          <SettingsRow
            icon={<Info size={15} color={PALETTE.blueDark} />}
            label="About"
            onClick={() => onOpenAbout("about")}
            right={<ChevronRight size={14} color="#94A3B8" />}
          />
          <SettingsRow
            icon={<FileText size={15} color={PALETTE.blueDark} />}
            label="Privacy Policy"
            onClick={() => onOpenAbout("privacy")}
            right={<ChevronRight size={14} color="#94A3B8" />}
          />
          <SettingsRow icon={<HelpCircle size={15} color={PALETTE.blueDark} />} label="Help & Support" right={<ChevronRight size={14} color="#94A3B8" />} last />
        </div>
      </div>

      <div className="px-4 mt-5">
        <button className="w-full py-3.5 rounded-2xl text-[13px] font-bold flex items-center justify-center gap-2 active:scale-[0.98] transition-transform" style={{ background: "#FEE2E2", color: "#DC2626" }}>
          <LogOut size={15} /> Logout
        </button>
      </div>
    </div>
  );
}

function SettingsScreen({ onBack, language, onOpenLanguage, darkMode, setDarkMode, onOpenAbout }) {
  const [liveDetection, setLiveDetection] = useState(true);
  const [notif, setNotif] = useState(true);
  return (
    <div className="h-full overflow-y-auto" style={{ background: PALETTE.bg }}>
      <BackBar onBack={onBack} title="Settings" />
      <div className="px-4 pb-8">
        <div className="rounded-[20px] bg-white overflow-hidden" style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}>
          <SettingsRow
            icon={<Shield size={15} color={PALETTE.blueDark} />}
            label="Live Detection"
            right={<Switch on={liveDetection} onClick={() => setLiveDetection(!liveDetection)} size="sm" />}
          />
          <SettingsRow
            icon={<Bell size={15} color={PALETTE.blueDark} />}
            label="Notifications"
            right={<Switch on={notif} onClick={() => setNotif(!notif)} size="sm" />}
          />
          <SettingsRow
            icon={<Moon size={15} color={PALETTE.blueDark} />}
            label="Theme"
            right={<Switch on={darkMode} onClick={() => setDarkMode(!darkMode)} size="sm" />}
          />
          <SettingsRow
            icon={<Globe size={15} color={PALETTE.blueDark} />}
            label="Language"
            onClick={onOpenLanguage}
            right={<span className="text-[11.5px] text-slate-400 flex items-center gap-1">{language} <ChevronRight size={13} /></span>}
          />
          <SettingsRow
            icon={<FileText size={15} color={PALETTE.blueDark} />}
            label="Privacy Policy"
            onClick={() => onOpenAbout("privacy")}
            right={<ChevronRight size={14} color="#94A3B8" />}
          />
          <SettingsRow
            icon={<FileText size={15} color={PALETTE.blueDark} />}
            label="Terms & Conditions"
            right={<ChevronRight size={14} color="#94A3B8" />}
          />
          <SettingsRow
            icon={<Info size={15} color={PALETTE.blueDark} />}
            label="About NeuroSync Guard"
            onClick={() => onOpenAbout("about")}
            right={<ChevronRight size={14} color="#94A3B8" />}
            last
          />
        </div>
      </div>
    </div>
  );
}

function LanguageScreen({ onBack, language, onSelect }) {
  return (
    <div className="h-full overflow-y-auto" style={{ background: PALETTE.bg }}>
      <BackBar onBack={onBack} title="Choose Your Language" />
      <div className="px-4 pb-8 space-y-2">
        {languages.map((lang) => (
          <button
            key={lang}
            onClick={() => onSelect(lang)}
            className="w-full flex items-center justify-between rounded-2xl px-4 py-3.5 bg-white active:scale-[0.98] transition-transform"
            style={{ boxShadow: "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)" }}
          >
            <span className="text-[13.5px] font-medium text-slate-900">{lang}</span>
            {language === lang && <CheckCircle2 size={17} color={PALETTE.blue} />}
          </button>
        ))}
      </div>
    </div>
  );
}

function Drawer({ open, onClose, onNavigate }) {
  const items = [
    { key: "dashboard", label: "Dashboard", icon: <Home size={16} /> },
    { key: "history", label: "History", icon: <HistoryIcon size={16} /> },
    { key: "upload", label: "Upload Recording", icon: <Upload size={16} /> },
    { key: "settings", label: "Settings", icon: <Settings size={16} /> },
    { key: "profile", label: "Profile", icon: <User size={16} /> },
    { key: "about", label: "About", icon: <Info size={16} /> },
  ];
  return (
    <>
      <div
        onClick={onClose}
        className="absolute inset-0 transition-opacity duration-200"
        style={{ background: "rgba(15,23,42,0.45)", zIndex: 110, opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
      />
      <div
        className="absolute top-0 left-0 h-full transition-transform duration-300"
        style={{ width: 270, background: "white", zIndex: 120, transform: open ? "translateX(0)" : "translateX(-100%)", boxShadow: "14px 0 36px rgba(0,0,0,0.15)" }}
      >
        <div className="px-5 pt-12 pb-6" style={{ background: "linear-gradient(160deg, #2563EB 0%, #1E3A8A 100%)" }}>
          <div className="rounded-2xl flex items-center justify-center mb-2.5" style={{ width: 48, height: 48, background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)" }}>
            <Shield size={20} color="white" />
          </div>
          <div className="text-white text-[14.5px] font-bold">NeuroSync Guard</div>
          <div className="text-white/60 text-[10.5px] mt-0.5">Arjun Mehta</div>
        </div>
        <div className="py-3">
          {items.map((item) => (
            <button
              key={item.key}
              onClick={() => { onNavigate(item.key); onClose(); }}
              className="w-full text-left px-5 py-3 text-[13px] font-medium flex items-center gap-3 text-slate-900 active:bg-slate-50 transition-colors"
            >
              {item.icon} {item.label}
            </button>
          ))}
          <div className="h-px bg-slate-100 my-2 mx-5" />
          <button className="w-full text-left px-5 py-3 text-[13px] font-semibold flex items-center gap-3 active:bg-slate-50 transition-colors" style={{ color: "#DC2626" }}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </div>
    </>
  );
}

function BottomNav({ active, onChange }) {
  const items = [
    { key: "dashboard", label: "Dashboard", icon: Home },
    { key: "history", label: "History", icon: HistoryIcon },
    { key: "alerts", label: "Alerts", icon: Bell },
    { key: "profile", label: "Profile", icon: User },
  ];
  return (
    <div
      className="absolute bottom-0 left-0 right-0 flex items-center justify-around bg-white"
      style={{ height: 68, borderTop: "1px solid #F1F5F9", boxShadow: "0 -4px 16px rgba(15,23,42,0.06)" }}
    >
      {items.map(({ key, label, icon: Icon }) => {
        const isActive = active === key;
        return (
          <button key={key} onClick={() => onChange(key)} className="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <Icon size={19} color={isActive ? PALETTE.blue : "#94A3B8"} />
            <span className="text-[10px] font-semibold" style={{ color: isActive ? PALETTE.blue : "#94A3B8" }}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}

function FakeCallIncomingOverlay({ caller, onAccept, onReject }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-4" style={{ background: "rgba(15,23,42,0.88)", zIndex: 220 }}>
      <div className="w-full max-w-[346px] flex flex-col items-center gap-4 rounded-[38px] bg-slate-950/95 p-5">
        <div className="rounded-full border border-white/15 bg-slate-900/85 flex items-center justify-center" style={{ width: 206, height: 206 }}>
          <div className="rounded-full bg-slate-200/90 shadow-[0_0_0_16px_rgba(148,163,184,0.10)]" style={{ width: 118, height: 118 }} />
        </div>

        <div className="text-center">
          <div className="text-[24px] font-extrabold text-white">{caller.callerName}</div>
          <div className="text-[13px] text-slate-300 mt-2">{caller.number}</div>
        </div>

        <div className="grid grid-cols-2 gap-3 w-full">
          <div className="rounded-[26px] bg-white/5 border border-white/10 p-3 flex flex-col items-center gap-2">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-800 text-white">
              <FileText size={18} />
            </div>
            <div className="text-[11px] text-slate-300">Messages</div>
          </div>
          <div className="rounded-[26px] bg-white/5 border border-white/10 p-3 flex flex-col items-center gap-2">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-800 text-white">
              <Bell size={18} />
            </div>
            <div className="text-[11px] text-slate-300">Reminder</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 w-full mt-2">
          <button
            onClick={onReject}
            className="rounded-full bg-slate-200 py-3 text-sm font-semibold text-slate-950 transition-transform duration-150 active:scale-95"
          >
            Decline
          </button>
          <button
            onClick={onAccept}
            className="rounded-full bg-emerald-500 py-3 text-sm font-semibold text-white transition-transform duration-150 active:scale-95"
          >
            Accept
          </button>
        </div>

        <div className="text-[12px] text-slate-400">Silent</div>
      </div>
    </div>
  );
}

function FakeCallActiveOverlay({ caller, onEnd, callSeconds }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-4" style={{ background: "rgba(15,23,42,0.95)", zIndex: 140 }}>
      <div className="w-full max-w-[360px] flex h-full flex-col justify-between py-5">
        <div className="flex justify-center">
          <span className="rounded-full bg-slate-900/80 px-3 py-2 text-[11px] uppercase tracking-[0.35em] text-slate-400">
            {formatDuration(callSeconds)}
          </span>
        </div>

        <div className="flex flex-col items-center gap-4">
          <div className="rounded-full bg-slate-900/80 flex items-center justify-center" style={{ width: 142, height: 142 }}>
            <div className="rounded-full bg-slate-200" style={{ width: 94, height: 94 }} />
          </div>
          <div className="text-[26px] font-semibold text-white">{caller.callerName}</div>
          <div className="text-[14px] text-slate-400">{caller.number}</div>
        </div>

        <div className="grid grid-cols-3 gap-3 w-full">
          <CallAction icon={<Mic size={20} />} label="Mute" />
          <CallAction icon={<Grid size={20} />} label="Keypad" />
          <CallAction icon={<Volume2 size={20} />} label="Speaker" />
        </div>

        <div className="grid grid-cols-3 gap-3 w-full">
          <CallAction icon={<Video size={20} />} label="Video" />
          <CallAction icon={<PhoneCall size={20} />} label="Add call" />
          <CallAction icon={<User size={20} />} label="Contacts" />
        </div>

        <button
          type="button"
          onClick={onEnd}
          className="w-full rounded-full bg-red-500 px-4 py-4 text-sm font-semibold text-white"
        >
          End Call
        </button>

        <audio autoPlay loop src="/sos.wav" style={{ display: "none" }} />
      </div>
    </div>
  );
}

function CallAction({ icon, label }) {
  return (
    <div className="rounded-[24px] bg-slate-800/90 p-3 text-slate-100">
      <div className="flex items-center justify-center mb-2 text-slate-100">{icon}</div>
      <div className="text-[11px] font-semibold">{label}</div>
    </div>
  );
}

function FakeCallAnalyzingOverlay() {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-4" style={{ background: "rgba(255,255,255,0.02)", zIndex: 230 }}>
      <div className="rounded-3xl bg-white/95 px-7 py-6 text-center shadow-2xl ring-1 ring-slate-200">
        <svg width="64" height="64" viewBox="0 0 44 44" className="mx-auto mb-3">
          <g fill="none" fillRule="evenodd" strokeWidth="3">
            <circle cx="22" cy="22" r="18" stroke="#BFDBFE" strokeOpacity="0.3" />
            <path d="M22 4a18 18 0 0 1 0 36" stroke="#2563EB">
              <animateTransform attributeName="transform" type="rotate" from="0 22 22" to="360 22 22" dur="1s" repeatCount="indefinite" />
            </path>
          </g>
        </svg>
        <div className="text-[16px] font-semibold text-slate-900">Analyzing Audio...</div>
        <div className="text-[12px] text-slate-600 mt-2">Please keep the app open</div>
      </div>
    </div>
  );
}

function FakeCallWarningOverlay({ onDashboard, onReturn }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-4" style={{ background: "rgba(15,23,42,0.72)", zIndex: 240 }}>
      <div className="w-full max-w-[360px] rounded-[32px] bg-sky-600 p-6 text-white shadow-2xl ring-1 ring-white/15">
        <div className="text-[11px] uppercase tracking-[0.25em] text-sky-100/80 mb-3">Warning</div>
        <div className="text-[22px] font-bold mb-4">Potential Scam Detected</div>
        <div className="text-[14px] leading-relaxed text-sky-100/90 mb-6">
          The call is under review and may be fraudulent. Stay on the line only if you are sure this is a trusted contact.
        </div>
        <div className="grid gap-3">
          <button
            type="button"
            onClick={onDashboard}
            className="w-full rounded-full bg-white px-4 py-3 text-sm font-semibold text-slate-950"
          >
            Back to Dashboard
          </button>
          <button
            type="button"
            onClick={onReturn}
            className="w-full rounded-full border border-white/30 bg-sky-700/95 px-4 py-3 text-sm font-semibold text-white"
          >
            Back to Call
          </button>
        </div>
      </div>
    </div>
  );
}

function FakeCallButton({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="fixed z-50 flex items-center gap-2 rounded-full bg-[#DBEAFE] px-4 py-3 text-sm font-semibold text-[#1D4ED8] shadow-[0_16px_32px_-18px_rgba(59,130,246,0.9)] transition-transform active:scale-[0.97]"
      style={{ bottom: 28, right: 28 }}
    >
      <PhoneCall size={16} />
      Generate Call
    </button>
  );
}

/* ---------------------------------------------------------
   ROOT APP
--------------------------------------------------------- */

export default function NeuroSyncGuard() {
  const [booted, setBooted] = useState(false);
  const [tab, setTab] = useState("dashboard");
  const [subScreen, setSubScreen] = useState(null);
  const [selectedCall, setSelectedCall] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [protectionOn, setProtectionOn] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [language, setLanguage] = useState("English");
  const [historyData, setHistoryData] = useState(MOCK_HISTORY_DATA);
  const [profile, setProfile] = useState(MOCK_PROFILE);
  const [aboutInfo, setAboutInfo] = useState(MOCK_ABOUT_INFO);
  const [aboutMode, setAboutMode] = useState("about");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [fakeCallMode, setFakeCallMode] = useState("idle");
  const [showAnalyzing, setShowAnalyzing] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const analyzingTimerRef = useRef(null);
  const [callSeconds, setCallSeconds] = useState(0);
  const callTimerRef = useRef(null);
  const analyzingTimeoutRef = useRef(null);
  const warningTimeoutRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => setBooted(true), 2000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    fetchHistory();
    fetchProfile();
    fetchAbout();
  }, []);

  async function fetchHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/history`);
      const payload = await response.json();
      if (response.ok && payload.history) {
        setHistoryData(payload.history.map((entry) => ({
          ...entry,
          prediction: normalizePrediction(entry.prediction),
        })));
      }
    } catch (err) {
      console.warn("Unable to load history", err);
      setHistoryData(MOCK_HISTORY_DATA);
    }
  }

  async function fetchProfile() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/profile`);
      const payload = await response.json();
      if (response.ok) {
        setProfile(payload);
      }
    } catch (err) {
      console.warn("Unable to load profile", err);
      setProfile(MOCK_PROFILE);
    }
  }

  async function fetchAbout() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/about`);
      const payload = await response.json();
      if (response.ok) {
        setAboutInfo(payload);
      }
    } catch (err) {
      console.warn("Unable to load about info", err);
      setAboutInfo(MOCK_ABOUT_INFO);
    }
  }

  function handleDrawerNav(key) {
    if (key === "upload") setSubScreen("upload");
    else if (key === "settings") setSubScreen("settings");
    else if (key === "about") {
      setAboutMode("about");
      setSubScreen("about");
    } else { setTab(key); setSubScreen(null); }
  }

  function openCall(call) {
    setSelectedCall(call);
    setSubScreen("callDetails");
  }

  function resetFakeCall() {
    setFakeCallMode("idle");
    setShowAnalyzing(false);
    setShowWarning(false);
    setCallSeconds(0);
    if (callTimerRef.current) { clearInterval(callTimerRef.current); callTimerRef.current = null; }
    if (analyzingTimeoutRef.current) { clearTimeout(analyzingTimeoutRef.current); analyzingTimeoutRef.current = null; }
    if (warningTimeoutRef.current) { clearTimeout(warningTimeoutRef.current); warningTimeoutRef.current = null; }
    if (analyzingTimerRef.current) { clearTimeout(analyzingTimerRef.current); analyzingTimerRef.current = null; }
  }

  function startFakeCall() {
    resetFakeCall();
    setFakeCallMode("incoming");
  }

  function acceptFakeCall() {
    // Begin active call and start call-second counter
    setFakeCallMode("active");
    setShowAnalyzing(false);
    setShowWarning(false);
    setCallSeconds(0);
    if (callTimerRef.current) clearInterval(callTimerRef.current);
    callTimerRef.current = setInterval(() => {
      setCallSeconds((s) => s + 1);
    }, 1000);

    if (analyzingTimeoutRef.current) clearTimeout(analyzingTimeoutRef.current);
    if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current);

    // After 55 seconds of active call, display the analyzing state.
    analyzingTimeoutRef.current = setTimeout(() => {
      setShowAnalyzing(true);
      warningTimeoutRef.current = setTimeout(() => {
        setShowAnalyzing(false);
        setShowWarning(true);
      }, 3000);
    }, 55000);
  }

  function rejectFakeCall() {
    resetFakeCall();
  }

  function endFakeCall() {
    resetFakeCall();
  }

  useEffect(() => {
    return () => {
      if (analyzingTimerRef.current) { clearTimeout(analyzingTimerRef.current); }
      if (analyzingTimeoutRef.current) { clearTimeout(analyzingTimeoutRef.current); }
      if (warningTimeoutRef.current) { clearTimeout(warningTimeoutRef.current); }
      if (callTimerRef.current) { clearInterval(callTimerRef.current); }
    };
  }, []);

  const shouldShowBottomNav = booted && !analysisResult && !subScreen && ["dashboard", "history", "alerts", "profile"].includes(tab);

  let content;
  if (!booted) {
    content = <SplashScreen />;
  } else if (analysisResult) {
    content = <ResultScreen result={analysisResult} onBack={() => { setAnalysisResult(null); setSubScreen(null); setTab("dashboard"); }} />;
  } else if (subScreen === "callDetails") {
    content = <CallDetailsScreen call={selectedCall} onBack={() => setSubScreen(null)} />;
  } else if (subScreen === "upload") {
    content = <UploadScreen onBack={() => setSubScreen(null)} onResult={(result) => setAnalysisResult(result)} refreshHistory={fetchHistory} />;
  } else if (subScreen === "about") {
    content = <AboutScreen onBack={() => setSubScreen(null)} aboutInfo={aboutInfo} aboutMode={aboutMode} />;
  } else if (subScreen === "settings") {
    content = (
      <SettingsScreen
        onBack={() => setSubScreen(null)}
        language={language}
        onOpenLanguage={() => setSubScreen("language")}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        onOpenAbout={(mode) => { setAboutMode(mode); setSubScreen("about"); }}
      />
    );
  } else if (subScreen === "language") {
    content = (
      <LanguageScreen
        onBack={() => setSubScreen(null)}
        language={language}
        onSelect={(lang) => { setLanguage(lang); setSubScreen(null); }}
      />
    );
  } else if (tab === "history") {
    content = <HistoryScreen historyData={historyData} />;
  } else if (tab === "alerts") {
    content = <AlertsScreen historyData={historyData} />;
  } else if (tab === "profile") {
    content = (
      <ProfileScreen
        profile={profile}
        protectionOn={protectionOn}
        setProtectionOn={setProtectionOn}
        language={language}
        onOpenLanguage={() => setSubScreen("language")}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        onOpenAbout={(mode) => { setAboutMode(mode); setSubScreen("about"); }}
      />
    );
  } else if (tab === "dashboard") {
    content = (
      <DashboardScreen
        onMenu={() => setDrawerOpen(true)}
        protectionOn={protectionOn}
        setProtectionOn={setProtectionOn}
        onOpenCall={openCall}
        onFakeCall={startFakeCall}
        recentCalls={historyData.length > 0 ? historyData : MOCK_RECENT_CALLS}
      />
    );
  }

  return (
    <div
      className="relative min-h-screen w-full overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.22),_transparent_30%),linear-gradient(135deg,_#f5f8ff_0%,_#eef4ff_45%,_#f8fbff_100%)]"
      style={{ minHeight: "100vh" }}
    >
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute left-[-4%] top-[-8%] h-56 w-56 rounded-full bg-blue-400/25 blur-3xl" />
        <div className="absolute bottom-[-6%] right-[-5%] h-72 w-72 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute inset-0 opacity-60" style={{ backgroundImage: "radial-gradient(rgba(37, 99, 235, 0.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
      </div>
      <div className="relative z-10 flex min-h-screen w-full items-center justify-center px-4 py-8 sm:px-6 lg:px-10">
        <div
          className="relative rounded-[40px] overflow-visible"
          style={{ width: 390, height: 844, background: "#121317", padding: 9, boxShadow: "0 36px 70px -20px rgba(0,0,0,0.4)" }}
        >
          <div className="relative w-full h-full rounded-[32px] overflow-hidden bg-white" style={filterStyle}>
          <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-5 text-[10px] font-medium" style={{ height: 26, zIndex: 90, color: "#0F172A" }}>
            <span>9:41</span>
            <span className="flex items-center gap-1.5"><span>●●●</span><span>📶</span><span>🔋</span></span>
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 rounded-full bg-black" style={{ top: 10, width: 10, height: 10, zIndex: 100 }} />

          <div className="absolute inset-0" style={{ paddingTop: 26 }}>
            {content}
          </div>

          {shouldShowBottomNav && <BottomNav active={tab} onChange={(k) => setTab(k)} />}
          {fakeCallMode === "incoming" && <FakeCallIncomingOverlay caller={MOCK_FAKE_CALL} onAccept={acceptFakeCall} onReject={rejectFakeCall} />}
          {fakeCallMode === "active" && <FakeCallActiveOverlay caller={MOCK_FAKE_CALL} onEnd={endFakeCall} callSeconds={callSeconds} />}
          {showAnalyzing && <FakeCallAnalyzingOverlay />}
          {showWarning && <FakeCallWarningOverlay onDashboard={() => { resetFakeCall(); setTab("dashboard"); }} onReturn={() => setShowWarning(false)} />}

          {booted && <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onNavigate={handleDrawerNav} />}
        </div>
        </div>
      </div>
      {tab === "dashboard" && fakeCallMode === "idle" && !analysisResult && !subScreen && booted && (
        <FakeCallButton onClick={startFakeCall} />
      )}
    </div>
  );
} 
