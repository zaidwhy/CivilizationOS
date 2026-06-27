import { useEffect, useState } from "react";

type CausalEvent = {
  id: string;
  text: string;
  tick: number;
  kind: string;
  institution_id: string | null;
};

const KIND_COLOR: Record<string, string> = {
  crisis:     "#f87171",
  emergent:   "#fb923c",
  decision:   "#fbbf24",
  resolution: "#4ade80",
  event:      "#34d399",
};

const KIND_ICON: Record<string, string> = {
  crisis:     "⚠",
  emergent:   "⚡",
  decision:   "⚖",
  resolution: "✓",
  event:      "●",
};

const INST_SHORT: Record<string, string> = {
  inst_gov:     "GOV",
  inst_economy: "ECO",
  inst_health:  "HEALTH",
  inst_media:   "MEDIA",
  inst_police:  "LAW",
};

export default function Timeline() {
  const [events, setEvents] = useState<CausalEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [scrub, setScrub] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        const res = await fetch("/api/timeline?k=200");
        if (res.ok) {
          const d = await res.json();
          setEvents(d.events ?? []);
          setTotal(d.total_nodes ?? 0);
        }
      } catch { /* ignore */ }
    };
    fetchTimeline();
    const id = setInterval(fetchTimeline, 8000);
    return () => clearInterval(id);
  }, []);

  if (events.length === 0) return null;

  const maxTick = Math.max(...events.map(e => e.tick), 1);
  const visible = scrub !== null ? events.filter(e => e.tick <= scrub) : events;

  return (
    <div className="panel" style={{ borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "#a78bfa", letterSpacing: 1 }}>
          ⏪ STORY REWIND
        </h3>
        <span style={{ fontSize: 10, color: "#475569" }}>{total} graph nodes</span>
      </div>

      {/* Tick scrubber */}
      <div style={{ marginBottom: 10 }}>
        <div style={{
          display: "flex", justifyContent: "space-between",
          fontSize: 9, color: "#475569", marginBottom: 3,
        }}>
          <span>t0</span>
          <span style={{ color: scrub !== null ? "#a78bfa" : "#475569" }}>
            {scrub !== null ? `◈ rewound to t${scrub}` : "▶ live history"}
          </span>
          <span>t{maxTick}</span>
        </div>
        <input
          type="range"
          min={0}
          max={maxTick}
          value={scrub ?? maxTick}
          onChange={(e) => {
            const v = Number(e.target.value);
            setScrub(v >= maxTick ? null : v);
          }}
          style={{ width: "100%", accentColor: "#a78bfa", cursor: "pointer" }}
        />
        {scrub !== null && (
          <button
            onClick={() => setScrub(null)}
            style={{
              background: "none", border: "none", color: "#a78bfa",
              fontSize: 9, cursor: "pointer", padding: "2px 0",
            }}
          >
            ↩ return to present
          </button>
        )}
      </div>

      {/* Event spine */}
      <div style={{ maxHeight: 260, overflowY: "auto", position: "relative" }}>
        <div style={{
          position: "absolute", left: 11, top: 4, bottom: 4,
          width: 1, background: "var(--line)",
        }} />

        {visible.length === 0 && (
          <div style={{ fontSize: 11, color: "#475569", textAlign: "center", padding: "16px 0" }}>
            No events before tick {scrub}
          </div>
        )}

        {visible.map((e) => {
          const color = KIND_COLOR[e.kind] ?? "#475569";
          const icon = KIND_ICON[e.kind] ?? "·";
          const inst = e.institution_id
            ? INST_SHORT[e.institution_id] ?? e.institution_id.replace("inst_", "").toUpperCase()
            : null;
          const isExpanded = expandedId === e.id;

          return (
            <div
              key={e.id}
              onClick={() => setExpandedId(isExpanded ? null : e.id)}
              style={{
                display: "flex", gap: 10, alignItems: "flex-start",
                paddingBottom: 8, cursor: "pointer",
              }}
            >
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: `${color}22`, border: `1.5px solid ${color}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, fontSize: 9, color, zIndex: 1,
              }}>
                {icon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 5, alignItems: "baseline", marginBottom: 1 }}>
                  <span style={{ fontSize: 9, color: "#475569" }}>t{e.tick}</span>
                  {inst && (
                    <span style={{
                      fontSize: 8, padding: "0 4px", borderRadius: 3,
                      background: `${color}22`, color, letterSpacing: 0.5,
                    }}>
                      {inst}
                    </span>
                  )}
                  {isExpanded && (
                    <span style={{ fontSize: 8, color: "#475569" }}>▲ collapse</span>
                  )}
                </div>
                {isExpanded ? (
                  <div style={{
                    fontSize: 11, color: "#e2e8f0", lineHeight: 1.55,
                    animation: "fade-in 0.15s ease-out",
                  }}>
                    {e.text}
                  </div>
                ) : (
                  <div style={{
                    fontSize: 11,
                    color: e.kind === "decision" ? "#fbbf24" : "#94a3b8",
                    lineHeight: 1.4,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}>
                    {e.text}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
