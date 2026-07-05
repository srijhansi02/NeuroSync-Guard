import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Lock, Mic, PhoneCall, ShieldCheck, Sparkles, Waves } from "lucide-react";
import { useNavigate } from "react-router-dom";

const PALETTE = {
  blue: "#2563EB",
  blueDark: "#1E3A8A",
  bg: "#F5F7FB",
};

const awarenessPoints = [
  "AI voice cloning can imitate trusted people with unsettling realism.",
  "Voice changer software can alter someone's voice during a live call.",
  "Fraudsters often create panic or urgency to steal sensitive information.",
  "AI-generated voices are becoming increasingly realistic.",
  "NeuroSync Guard helps analyze voice recordings to detect these threats.",
];

const fraudTypes = [
  {
    title: "AI Clone / AI Voice Generator",
    description:
      "Attackers use artificial intelligence to clone or generate someone's voice and impersonate trusted individuals during calls.",
    icon: Sparkles,
  },
  {
    title: "Real Human Fraud",
    description:
      "Some attackers rely on emotional pressure, social engineering, and impersonation without using AI-generated voices.",
    icon: AlertTriangle,
  },
];

const cardShadow = "0 2px 4px rgba(15,23,42,0.04), 0 6px 16px -6px rgba(15,23,42,0.10)";

function AnimatedThreatFlow() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      style={{
        background: "white",
        border: "1px solid #E2E8F0",
        boxShadow: cardShadow,
      }}
      className="relative overflow-hidden rounded-[28px] p-5"
    >
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(135deg, rgba(37,99,235,0.08), rgba(30,58,138,0.04))`,
        }}
      />
      <div className="relative z-10 flex flex-col gap-3">
        <div className="flex items-center gap-2 rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ background: "#EEF2FF", color: PALETTE.blueDark }}>
          <ShieldCheck size={13} />
          Threat pattern preview
        </div>

        <div className="flex items-center justify-between gap-3 rounded-[20px] border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-3">
            <motion.div
              animate={{ y: [0, -4, 0], rotate: [0, -2, 0] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              className="flex h-12 w-12 items-center justify-center rounded-2xl text-white"
              style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})` }}
            >
              <PhoneCall size={18} />
            </motion.div>
            <div>
              <div className="text-[13px] font-semibold text-slate-900">Incoming call</div>
              <div className="text-[11px] text-slate-500">Voice fraud attempt detected</div>
            </div>
          </div>
          <div className="flex items-end gap-1.5">
            {[8, 12, 10, 14, 9].map((height, index) => (
              <motion.span
                key={index}
                animate={{ height: [height, height + 5, height] }}
                transition={{ duration: 1.1 + index * 0.08, repeat: Infinity, ease: "easeInOut" }}
                className="w-1.5 rounded-full"
                style={{ height, background: `linear-gradient(180deg, ${PALETTE.blue}, #93C5FD)` }}
              />
            ))}
          </div>
        </div>

        <div className="rounded-[20px] border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full" style={{ background: "#DBEAFE" }}>
                <Mic size={16} color={PALETTE.blueDark} />
              </div>
              <div>
                <div className="text-[12px] font-semibold text-slate-900">AI voice pattern</div>
                <div className="text-[11px] text-slate-500">Synthetic waveform detected</div>
              </div>
            </div>
            <div className="flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[10px] font-semibold" style={{ background: "#EFF6FF", color: PALETTE.blue }}>
              <Waves size={12} />
              Digital wave
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
            <motion.div
              animate={{ x: ["-110%", "110%"] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
              className="h-full rounded-full"
              style={{ background: `linear-gradient(90deg, ${PALETTE.blue}, #7DD3FC)` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between rounded-[20px] border border-slate-200 bg-slate-50 p-3">
          <div className="text-[12px] font-semibold text-slate-900">Security shield intercepts the attack</div>
          <motion.div
            animate={{ scale: [0.96, 1, 0.96] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            className="flex h-11 w-11 items-center justify-center rounded-2xl text-white"
            style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})` }}
          >
            <ShieldCheck size={18} />
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}

function FeatureCard({ title, description, icon: Icon }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.45 }}
      style={{
        background: "white",
        border: "1px solid #E2E8F0",
        boxShadow: cardShadow,
      }}
      className="rounded-[24px] p-5"
    >
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl text-white" style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})` }}>
        <Icon size={18} />
      </div>
      <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-[13px] leading-6 text-slate-600">{description}</p>
    </motion.article>
  );
}

export default function AwarenessPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen" style={{ background: `linear-gradient(135deg, ${PALETTE.bg} 0%, #EEF2FF 60%, #F8FAFC 100%)`, color: "#0F172A" }}>
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          animate={{ x: [0, 16, 0], y: [0, -10, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          className="absolute left-[-5%] top-[-6%] h-48 w-48 rounded-full blur-3xl"
          style={{ background: "rgba(37,99,235,0.16)" }}
        />
        <motion.div
          animate={{ x: [0, -18, 0], y: [0, 12, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-[-8%] right-[-4%] h-56 w-56 rounded-full blur-3xl"
          style={{ background: "rgba(34,211,238,0.12)" }}
        />
      </div>

      <main className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <header className="mb-6 flex items-center justify-between rounded-full border border-slate-200 bg-white/80 px-3 py-2.5 shadow-sm backdrop-blur" style={{ boxShadow: "0 2px 8px rgba(15,23,42,0.04)" }}>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full text-white" style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})` }}>
              <Lock size={16} />
            </div>
            <div>
              <div className="text-[13px] font-semibold text-slate-900">NeuroSync Guard</div>
              <div className="text-[11px] text-slate-500">Voice fraud awareness</div>
            </div>
          </div>
          <div className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em]" style={{ color: PALETTE.blueDark }}>
            Security Brief
          </div>
        </header>

        <section className="grid items-center gap-6 lg:grid-cols-[1.02fr_0.98fr]">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-[12px] font-medium" style={{ color: PALETTE.blueDark, boxShadow: "0 2px 8px rgba(15,23,42,0.04)" }}>
              <Waves size={14} />
              Voice fraud awareness
            </div>
            <h1 className="mt-4 text-[30px] font-semibold leading-tight text-slate-950 sm:text-[36px] lg:text-[42px]">
              How AI Calling Scams Work
            </h1>
            <p className="mt-3 max-w-2xl text-[14px] leading-7 text-slate-600">
              Before experiencing NeuroSync Guard, understand how modern AI voice fraud works and how attackers manipulate victims using voice cloning and social engineering.
            </p>

            <motion.button
              whileHover={{ scale: 1.01, y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate("/mobile")}
              className="mt-5 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[13px] font-semibold text-white transition-all"
              style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})`, boxShadow: "0 16px 32px -18px rgba(37,99,235,0.9)" }}
            >
              Let&apos;s See
              <ArrowRight size={15} />
            </motion.button>
          </motion.div>

          <AnimatedThreatFlow />
        </section>

        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.6 }}
          style={{ background: "white", border: "1px solid #E2E8F0", boxShadow: cardShadow }}
          className="mt-6 rounded-[24px] p-5 sm:p-6"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl text-white" style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})` }}>
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-slate-900">How Voice Frauds Happen</h2>
              <p className="text-[12px] text-slate-500">A concise view of the most common tactics behind modern scams.</p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-[20px] border border-slate-200 bg-slate-50 p-4 text-[13px] leading-7 text-slate-600">
              Voice fraudsters often exploit trust, urgency, and familiarity to make real-time calls feel convincing. The goal is to pressure people into sharing OTPs, passwords, or bank information before they pause to verify the caller.
            </div>
            <ul className="space-y-2.5">
              {awarenessPoints.map((point, index) => (
                <li key={point} className="flex gap-3 rounded-[16px] border border-slate-200 bg-white px-3.5 py-3 text-[13px] text-slate-600" style={{ boxShadow: "0 1px 3px rgba(15,23,42,0.03)" }}>
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold" style={{ background: "#DBEAFE", color: PALETTE.blueDark }}>
                    {index + 1}
                  </span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </motion.section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          {fraudTypes.map((item) => (
            <FeatureCard key={item.title} title={item.title} description={item.description} icon={item.icon} />
          ))}
        </section>

        <div className="mt-6 flex justify-center pb-6">
          <motion.button
            whileHover={{ scale: 1.01, y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => navigate("/mobile")}
            className="inline-flex items-center gap-2 rounded-full px-6 py-3 text-[13px] font-semibold text-white transition-all"
            style={{ background: `linear-gradient(135deg, ${PALETTE.blue}, ${PALETTE.blueDark})`, boxShadow: "0 16px 32px -18px rgba(37,99,235,0.9)" }}
          >
            Let&apos;s See
            <ArrowRight size={15} />
          </motion.button>
        </div>
      </main>
    </div>
  );
}
