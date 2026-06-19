import { useEffect, useState } from "react";
import { useWorld, DebateTurn } from "../ws/store";

const INSTITUTIONS = [
  { id: "inst_gov",     label: "Government" },
  { id: "inst_economy", label: "Economy" },
  { id: "inst_health",  label: "Healthcare" },
  { id: "inst_media",   label: "Media" },
  { id: "inst_police",  label: "Police" },
];

type Template = {
  key: string;
  name: string;
  description: string;
  primary_institution: string;
  secondary_institutions: string[];
};

const ROLE_COLORS: Record<string, string> = {
  Historian:   "#a78bfa",
  Strategist:  "#34d399",
  Skeptic:     "#f87171",
  Predictor:   "#60a5fa",
  Synthesizer: "#fbbf24",
};

const CRISIS_EMOJI: Record<string, string> = {
  pandemic:   "🦠",
  drought:    "🌵",
  cyberattack:"💻",
  election:   "🗳️",
  crime_wave: "🔫",
};

function TurnCard({ turn }: { turn: DebateTurn }) {
  const color = ROLE_COLORS[turn.role] ?? "#94a3b8";
  return (
    <div style={{
      borderLeft: `3px solid ${color}`,
      padding: "8px 10px",
      marginBottom: 8,
      background: turn.is_final ? "rgba(251,191,36,0.08)" : "rgba(255,255,255,0.03)",
      borderRadius: "0 6px 6px 0",
    }}>
      <div style={{ fontSize: 11, color, fontWeight: 600, marginBottom: 4 }}>
        {turn.name}
        {turn.is_final && (
          <span style={{ marginLeft: 8, color: "#fbbf24", fontSize: 10 }}>★ VERDICT</span>
        )}
      </div>
      <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{turn.text}</div>
    </div>
  );
}

export default function CouncilChamber() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [institution, setInstitution] = useState("inst_health");
  const [crisisText, setCrisisText] = useState("");
  const [injecting, setInjecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debates = useWorld((s) => s.debates);
  const activeDebateId = useWorld((s) => s.activeDebateId);
  const activeTurns: DebateTurn[] = activeDebateId ? (debates[activeDebateId] ?? []) : [];
  const isComplete = activeTurns.some((t) => t.is_final);

  useEffect(() => {
    fetch("/api/events/templates")
      .then((r) => r.json())
      .then((d) => setTemplates(d.templates ?? []))
      .catch(() => {});
  }, []);

  function pickTemplate(key: string) {
    setSelectedTemplate(key);
    const t = templates.find((t) => t.key === key);
    if (t) {
      setCrisisText(t.description);
      setInstitution(t.primary_institution);
    }
  }

  async function inject() {
    if (!crisisText.trim()) return;
    setInjecting(true);
    setError(null);
    try {
      const res = await fetch("/api/crisis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: crisisText.trim(),
          institution_id: institution,
          template_key: selectedTemplate || null,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? `HTTP ${res.status}`);
      } else {
        setCrisisText("");
        setSelectedTemplate("");
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <h3 style={{ margin: 0, fontSize: 13, color: "#fbbf24", letterSpacing: 1 }}>
        ⚖ PANTHEON COUNCIL
      </h3>

      {/* Template presets */}
      {templates.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {templates.map((t) => (
            <button
              key={t.key}
              onClick={() => pickTemplate(t.key)}
              style={{
                background: selectedTemplate === t.key ? "#7c3aed" : "#1e293b",
                color: selectedTemplate === t.key ? "#fff" : "#94a3b8",
                border: "1px solid #334155",
                borderRadius: 4,
                padding: "3px 7px",
                fontSize: 11,
                cursor: "pointer",
              }}
            >
              {CRISIS_EMOJI[t.key] ?? "⚡"} {t.name}
            </button>
          ))}
        </div>
      )}

      {/* Manual form */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <select
          value={institution}
          onChange={(e) => setInstitution(e.target.value)}
          style={{
            background: "#1e293b", color: "#cbd5e1",
            border: "1px solid #334155", borderRadius: 4,
            padding: "4px 6px", fontSize: 12,
          }}
        >
          {INSTITUTIONS.map((inst) => (
            <option key={inst.id} value={inst.id}>{inst.label}</option>
          ))}
        </select>
        <textarea
          value={crisisText}
          onChange={(e) => setCrisisText(e.target.value)}
          placeholder="Describe the crisis… or pick a preset above"
          rows={2}
          style={{
            background: "#1e293b", color: "#cbd5e1",
            border: "1px solid #334155", borderRadius: 4,
            padding: "5px 7px", fontSize: 12,
            resize: "vertical", fontFamily: "inherit",
          }}
        />
        <button
          onClick={inject}
          disabled={injecting || !crisisText.trim()}
          style={{
            background: injecting ? "#334155" : "#7c3aed",
            color: "#fff", border: "none", borderRadius: 4,
            padding: "5px 10px", fontSize: 12,
            cursor: injecting ? "not-allowed" : "pointer", fontWeight: 600,
          }}
        >
          {injecting ? "Injecting…" : "⚡ Inject Crisis"}
        </button>
        {error && <div style={{ fontSize: 11, color: "#f87171" }}>Error: {error}</div>}
      </div>

      {/* Debate transcript */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {activeTurns.length === 0 ? (
          <div style={{ fontSize: 11, color: "#64748b", textAlign: "center", marginTop: 12 }}>
            No active debate.<br />Pick a preset or describe a crisis above.
          </div>
        ) : (
          <>
            <div style={{ fontSize: 10, color: "#64748b", marginBottom: 8 }}>
              Debate #{activeDebateId}
              {isComplete ? " · complete" : ` · ${activeTurns.length}/5 specialists…`}
            </div>
            {activeTurns.map((t, i) => <TurnCard key={i} turn={t} />)}
            {!isComplete && (
              <div style={{ fontSize: 11, color: "#64748b", textAlign: "center" }}>
                <span className="pill">deliberating…</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
