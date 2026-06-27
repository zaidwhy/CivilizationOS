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

const INST_COLORS: Record<string, string> = {
  inst_gov:     "#6b5db8",
  inst_economy: "#b07d3a",
  inst_health:  "#3a8a5c",
  inst_media:   "#4b7fa8",
  inst_police:  "#c96060",
};

const INST_LABELS: Record<string, string> = {
  inst_gov:     "Government",
  inst_economy: "Economy",
  inst_health:  "Healthcare",
  inst_media:   "Media",
  inst_police:  "Police",
};

const CRISIS_EMOJI: Record<string, string> = {
  pandemic:       "🦠",
  drought:        "🌵",
  cyberattack:    "💻",
  election:       "🗳️",
  crime_wave:     "🔫",
  housing_crisis: "🏚️",
  power_outage:   "⚡",
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

function CompletedDebateCard({
  turns, expanded, onToggle,
}: {
  turns: DebateTurn[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const verdict = turns.find((t) => t.is_final);
  const instId = turns[0]?.institution_id ?? "";
  const instColor = INST_COLORS[instId] ?? "#475569";
  const instLabel = INST_LABELS[instId] ?? instId.replace("inst_", "");
  const preview = verdict?.text.slice(0, 90) ?? turns[0]?.text?.slice(0, 90) ?? "";

  return (
    <div style={{
      marginBottom: 4, borderRadius: 6,
      border: `1px solid ${expanded ? instColor + "50" : "var(--line)"}`,
      overflow: "hidden", transition: "border-color 0.2s",
    }}>
      <div
        onClick={onToggle}
        style={{
          padding: "6px 10px",
          background: expanded ? `${instColor}10` : "rgba(255,255,255,0.02)",
          cursor: "pointer",
          display: "flex", alignItems: "center", gap: 8,
          borderLeft: `3px solid ${instColor}`,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 2 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
              color: instColor, textTransform: "uppercase",
            }}>
              {instLabel}
            </span>
            <span style={{ fontSize: 9, color: "#475569" }}>t{turns[0]?.tick ?? "?"}</span>
            <span style={{ fontSize: 9, color: "#fbbf24" }}>★ verdict</span>
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {preview}{preview.length >= 90 ? "…" : ""}
          </div>
        </div>
        <span style={{ fontSize: 10, color: "#475569", flexShrink: 0 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div style={{ padding: "8px", maxHeight: 260, overflowY: "auto", background: "rgba(0,0,0,0.2)" }}>
          {turns.map((t, i) => <TurnCard key={i} turn={t} />)}
        </div>
      )}
    </div>
  );
}

export default function CouncilChamber() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [customCrises, setCustomCrises] = useState<CrisisRecord[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [institution, setInstitution] = useState("inst_health");
  const [crisisText, setCrisisText] = useState("");
  const [injecting, setInjecting] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showOlderHistory, setShowOlderHistory] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const debates = useWorld((s) => s.debates);
  const activeDebateId = useWorld((s) => s.activeDebateId);
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];

  // Live = the most-recently-streaming debate if it has no verdict yet
  const activeTurns: DebateTurn[] = activeDebateId ? (debates[activeDebateId] ?? []) : [];
  const isActiveComplete = activeTurns.some((t) => t.is_final);
  const liveId = activeDebateId && !isActiveComplete ? activeDebateId : null;
  const liveTurns = liveId ? activeTurns : [];

  // Completed debates — newest first (Object.keys insertion order)
  const allDebateIds = Object.keys(debates);
  const completedIds = [...allDebateIds]
    .filter((id) => debates[id].some((t) => t.is_final))
    .reverse();
  const latestCompletedId = completedIds[0] ?? null;
  const olderIds = completedIds.slice(1);

  useEffect(() => {
    if (liveId) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveTurns.length, liveId]);

  useEffect(() => {
    fetch("/api/events/templates")
      .then((r) => r.json())
      .then((d) => setTemplates(d.templates ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fetchCrises = () => {
      fetch("/api/crises")
        .then((r) => r.json())
        .then((d: { crises: CrisisRecord[] }) => {
          setCustomCrises(
            (d.crises ?? []).filter((c) => !c.template_key && !c.resolved)
          );
        })
        .catch(() => {});
    };
    fetchCrises();
    const id = setInterval(fetchCrises, 8000);
    return () => clearInterval(id);
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

  async function resolveById(crisisId: string) {
    setResolving(crisisId);
    setError(null);
    try {
      const res = await fetch(`/api/crisis/id/${crisisId}/resolve`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? `HTTP ${res.status}`);
      } else {
        setCustomCrises((prev) => prev.filter((c) => c.id !== crisisId));
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setResolving(null);
    }
  }

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid var(--line)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "#fbbf24", letterSpacing: 1 }}>
          ⚖ PANTHEON COUNCIL
        </h3>
        {completedIds.length > 0 && (
          <span style={{ fontSize: 10, color: "#475569" }}>
            {completedIds.length} debate{completedIds.length !== 1 ? "s" : ""} archived
          </span>
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

      {/* Unresolved custom (free-text) crisis badges */}
      {customCrises.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontSize: 10, color: "#64748b" }}>Custom crises</div>
          {customCrises.map((c) => (
            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
              <span style={{
                fontSize: 10, padding: "2px 7px", borderRadius: 999,
                background: "rgba(251,191,36,0.12)", color: "#fbbf24",
                border: "1px solid rgba(251,191,36,0.3)",
                maxWidth: 170, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                ⚡ {c.text.slice(0, 40)}{c.text.length > 40 ? "…" : ""}
              </span>
              <button
                onClick={() => resolveById(c.id)}
                disabled={resolving === c.id}
                title={`Resolve custom crisis (${c.id})`}
                style={{
                  background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)",
                  color: "#4ade80", borderRadius: 4, fontSize: 9, cursor: "pointer",
                  padding: "1px 5px",
                }}
              >
                {resolving === c.id ? "…" : "✓ resolve"}
              </button>
            </div>
          ))}
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

      {/* Live debate — expanded, auto-scrolls */}
      {liveId ? (
        <div style={{ maxHeight: 280, overflowY: "auto" }}>
          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 8 }}>
            Debate #{liveId} · {liveTurns.length}/5 <Dots />
          </div>
          {liveTurns.map((t, i) => <TurnCard key={i} turn={t} />)}
          <div ref={bottomRef} />
        </div>
      ) : !latestCompletedId ? (
        <div style={{ fontSize: 11, color: "#64748b", textAlign: "center", marginTop: 12 }}>
          No active debate. Pick a preset or describe a crisis above.
        </div>
      ) : null}

      {/* Latest completed debate — collapsed card, click to expand */}
      {latestCompletedId && (
        <CompletedDebateCard
          turns={debates[latestCompletedId]}
          expanded={expandedId === latestCompletedId}
          onToggle={() =>
            setExpandedId(expandedId === latestCompletedId ? null : latestCompletedId)
          }
        />
      )}

      {/* Older debates — hidden behind accordion */}
      {olderIds.length > 0 && (
        <div>
          <button
            onClick={() => setShowOlderHistory((v) => !v)}
            style={{
              background: "none", border: "1px solid var(--line)", borderRadius: 4,
              color: "#64748b", fontSize: 10, cursor: "pointer",
              padding: "3px 8px", width: "100%",
            }}
          >
            {showOlderHistory
              ? "▲ hide older debates"
              : `▼ ${olderIds.length} older debate${olderIds.length !== 1 ? "s" : ""}`}
          </button>
          {showOlderHistory && (
            <div style={{ marginTop: 4, maxHeight: 200, overflowY: "auto" }}>
              {olderIds.map((id) => (
                <CompletedDebateCard
                  key={id}
                  turns={debates[id]}
                  expanded={expandedId === id}
                  onToggle={() => setExpandedId(expandedId === id ? null : id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
