import { useEffect, useState } from "react";

type TimelineEvent = {
  id: string;
  text: string;
  tick: number;
  kind: string;
  institution_id: string | null;
};

const KIND_COLOR: Record<string, string> = {
  crisis:     "#f87171",
  decision:   "#fbbf24",
  resolution: "#4ade80",
  event:      "#34d399",
};

const KIND_ICON: Record<string, string> = {
  crisis:     "⚠",
  decision:   "⚖",
  resolution: "✓",
  event:      "●",
};

const INST_SHORT: Record<string, string> = {
  inst_gov:     "GOV",
  inst_economy: "ECO",
  inst_health:  "MED",
  inst_media:   "MED",
  inst_police:  "LAW",
};

export default function Timeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        const res = await fetch("/api/timeline?k=40");
        if (res.ok) {
          const d = await res.json();
          setEvents(d.events ?? []);
          setTotal(d.total_nodes ?? 0);
        }
      } catch { /* ignore */ }
    };
    fetchTimeline();
    const id = setInterval(fetchTimeline, 6000);
    return () => clearInterval(id);
  }, []);

  if (events.length === 0) return null;

  return (
    <div className="panel" style={{ borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "#94a3b8", letterSpacing: 1 }}>
          🕰 CAUSAL TIMELINE
        </h3>
        <span style={{ fontSize: 10, color: "#475569" }}>{total} graph nodes</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 0, position: "relative" }}>
        {/* Vertical spine */}
        <div style={{
          position: "absolute", left: 11, top: 8, bottom: 8,
          width: 1, background: "var(--line)",
        }} />

        {events.map((e) => {
          const color = KIND_COLOR[e.kind] ?? "#475569";
          const icon = KIND_ICON[e.kind] ?? "·";
          const inst = e.institution_id ? INST_SHORT[e.institution_id] ?? e.institution_id : null;
          return (
            <div key={e.id} style={{ display: "flex", gap: 10, alignItems: "flex-start", paddingBottom: 8 }}>
              {/* dot on spine */}
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: color + "22", border: `1.5px solid ${color}`,
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
                      background: color + "22", color, letterSpacing: 0.5,
                    }}>
                      {inst}
                    </span>
                  )}
                </div>
                <div style={{
                  fontSize: 11, color: e.kind === "decision" ? "#fbbf24" : "#94a3b8",
                  lineHeight: 1.4,
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}>
                  {e.text}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
