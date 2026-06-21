import { useEffect, useRef, useState } from "react";
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
  resolution_text: string;
};

type CrisisRecord = {
  id: string;
  text: string;
  tick: number;
  institution_id: string;
  debate_id: string;
  severity: number;
  template_key: string | null;
  resolved: boolean;
};

const ROLE_COLORS: Record<string, string> = {
  Historian:   "#a78bfa",
  Strategist:  "#34d399",
  Skeptic:     "#f87171",
  Predictor:   "#60a5fa",
  Synthesizer: "#fbbf24",
};

const CRISIS_EMOJI: Record<string, string> = {
  pandemic:    "🦠",
  drought:     "🌵",
  cyberattack: "💻",
  election:    "🗳️",
  crime_wave:  "🔫",
};

function Dots() {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFrame((f) => (f + 1) % 4), 400);
    return () => clearInterval(id);
  }, []);
  return <span>{".".repeat(frame + 1)}</span>;
}

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
  const [resolving, setResolving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const debates = useWorld((s) => s.debates);
  const activeDebateId = useWorld((s) => s.activeDebateId);
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];
  const activeTurns: DebateTurn[] = activeDebateId ? (debates[activeDebateId] ?? []) : [];
  const isComplete = activeTurns.some((t) => t.is_final);

  // Scroll to bottom when new turns arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeTurns.length]);

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

  async function resolve(key: string) {
    setResolving(key);
    setError(null);
    try {
      const res = await fetch(`/api/crisis/${key}/resolve`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? `HTTP ${res.status}`);
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setResolving(null);
    }
  }

  const allDebateIds = Object.keys(debates);

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "#fbbf24", letterSpacing: 1 }}>
          ⚖ PANTHEON COUNCIL
        </h3>
        {allDebateIds.length > 1 && (
          <button
            onClick={() => setShowHistory(!showHistory)}
            style={{
              background: "none", border: "1px solid var(--line)", borderRadius: 4,
              color: "#64748b", fontSize: 10, cursor: "pointer", padding: "2px 6px",
            }}
          >
            {showHistory ? "current" : `history (${allDebateIds.length})`}
          </button>
        )}
      </div>

      {/* Active crisis badges with resolve buttons */}
      {activeCrises.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {activeCrises.map((name) => {
            const tmpl = templates.find((t) => t.name === name);
            return (
              <div key={name} style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <span style={{
                  fontSize: 10, padding: "2px 7px", borderRadius: 999,
                  background: "rgba(248,113,113,0.15)", color: "#f87171",
                  border: "1px solid rgba(248,113,113,0.3)",
                }}>
                  ⚠ {name}
                </span>
                {tmpl && (
                  <button
                    onClick={() => resolve(tmpl.key)}
                    disabled={resolving === tmpl.key}
                    title={`Resolve: ${tmpl.resolution_text}`}
                    style={{
                      background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)",
                      color: "#4ade80", borderRadius: 4, fontSize: 9, cursor: "pointer",
                      padding: "1px 5px",
                    }}
                  >
                    {resolving === tmpl.key ? "…" : "✓ resolve"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

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

      {/* Inject form */}
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
      {!showHistory ? (
        <div style={{ maxHeight: 320, overflowY: "auto", minHeight: 0 }}>
          {activeTurns.length === 0 ? (
            <div style={{ fontSize: 11, color: "#64748b", textAlign: "center", marginTop: 12 }}>
              No active debate. Pick a preset or describe a crisis above.
            </div>
          ) : (
            <>
              <div style={{ fontSize: 10, color: "#64748b", marginBottom: 8 }}>
                Debate #{activeDebateId}
                {isComplete
                  ? " · complete ✓"
                  : <> · {activeTurns.length}/5 <Dots /></>
                }
              </div>
              {activeTurns.map((t, i) => <TurnCard key={i} turn={t} />)}
              <div ref={bottomRef} />
            </>
          )}
        </div>
      ) : (
        <div style={{ maxHeight: 280, overflowY: "auto" }}>
          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 8 }}>All debates (newest first)</div>
          {[...allDebateIds].reverse().map((did) => {
            const turns = debates[did];
            const final = turns.find((t) => t.is_final);
            const inst = turns[0]?.institution_id ?? "";
            return (
              <div
                key={did}
                onClick={() => { useWorld.getState().setActiveDebate(did); setShowHistory(false); }}
                style={{
                  padding: "6px 8px", marginBottom: 4, borderRadius: 6,
                  background: did === activeDebateId ? "rgba(124,58,237,0.15)" : "rgba(255,255,255,0.03)",
                  border: `1px solid ${did === activeDebateId ? "#7c3aed" : "var(--line)"}`,
                  cursor: "pointer",
                }}
              >
                <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>
                  #{did} · {inst.replace("inst_", "")} {final ? "✓" : "⋯"}
                </div>
                <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.4 }}>
                  {final ? final.text.slice(0, 90) + "…" : turns[0]?.text?.slice(0, 60) + "…"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
