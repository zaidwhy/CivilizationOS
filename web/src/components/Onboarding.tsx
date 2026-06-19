import { useState } from "react";

const STEPS = [
  {
    title: "Welcome to CivilizationOS",
    body: "A living city of 10 AI citizens governed by 5 institutional councils. Watch society evolve — or break it yourself by injecting crises.",
    icon: "🏙️",
  },
  {
    title: "Citizens & the City Map",
    body: "Dots on the isometric map are citizens. They move on daily routines, talk to neighbours, form relationships, and build episodic memories. Click any citizen to inspect their mind.",
    icon: "👥",
  },
  {
    title: "The PANTHEON Council",
    body: "Scroll the right sidebar to ⚖ PANTHEON COUNCIL. Pick a crisis preset (Pandemic, Drought, etc.) and click Inject. Five AI specialists — Historian, Strategist, Skeptic, Predictor, Synthesizer — debate live.",
    icon: "⚖️",
  },
  {
    title: "TCMF: Novel RAG",
    body: "Each council debate is grounded by Temporal-Causal Memory Fusion — a retrieval system that fuses citizen episodic memories with the society-wide causal graph. The Historian literally argues from precedent.",
    icon: "🧠",
  },
  {
    title: "Speed & Cost",
    body: "Use the speed slider in the header to control tick rate. The spend counter shows live Claude API cost (free mode uses local Ollama + Gemini for $0). Change PREMIUM_MODE=true in .env to enable Claude for council debates.",
    icon: "⚡",
  },
];

const KEY = "civOS_onboarding_done_v1";

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(() => !localStorage.getItem(KEY));

  if (!visible) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  function dismiss() {
    localStorage.setItem(KEY, "1");
    setVisible(false);
  }

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(5,7,13,0.82)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "#141a24",
        border: "1px solid #232c3b",
        borderRadius: 12,
        padding: "32px 36px",
        maxWidth: 460,
        width: "90%",
        boxShadow: "0 24px 48px rgba(0,0,0,0.6)",
      }}>
        <div style={{ fontSize: 40, marginBottom: 16, textAlign: "center" }}>
          {current.icon}
        </div>
        <h2 style={{ margin: "0 0 10px", fontSize: 18, color: "#e6edf3", textAlign: "center" }}>
          {current.title}
        </h2>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "#8b97a7", lineHeight: 1.65, textAlign: "center" }}>
          {current.body}
        </p>

        {/* Step dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 6, marginBottom: 20 }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              onClick={() => setStep(i)}
              style={{
                width: i === step ? 20 : 6, height: 6, borderRadius: 999,
                background: i === step ? "#6ea8fe" : "#232c3b",
                cursor: "pointer", transition: "all 0.2s",
              }}
            />
          ))}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          {step > 0 && (
            <button
              onClick={() => setStep(step - 1)}
              style={{
                flex: 1, padding: "8px 0", borderRadius: 6,
                background: "transparent", border: "1px solid #232c3b",
                color: "#8b97a7", cursor: "pointer", fontSize: 13,
              }}
            >
              ← Back
            </button>
          )}
          <button
            onClick={isLast ? dismiss : () => setStep(step + 1)}
            style={{
              flex: 2, padding: "8px 0", borderRadius: 6,
              background: "#6ea8fe", border: "none",
              color: "#0b0e14", cursor: "pointer", fontSize: 13, fontWeight: 700,
            }}
          >
            {isLast ? "Let's go →" : "Next →"}
          </button>
        </div>

        <div style={{ textAlign: "center", marginTop: 12 }}>
          <button
            onClick={dismiss}
            style={{
              background: "none", border: "none", color: "#475569",
              fontSize: 11, cursor: "pointer", textDecoration: "underline",
            }}
          >
            Skip tour
          </button>
        </div>
      </div>
    </div>
  );
}
