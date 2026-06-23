import { useWorld } from "../ws/store";

const KIND_ICON: Record<string, string> = {
  conversation: "💬",
  crisis:       "⚠️",
  emergent:     "⚡",
  debate:       "⚖️",
  observation:  "👁",
  reflection:   "💭",
  event:        "📡",
  decision:     "✅",
};

const KIND_COLOR: Record<string, string> = {
  conversation: "#6ea8fe",
  crisis:       "#f87171",
  emergent:     "#fb923c",
  debate:       "#fbbf24",
  observation:  "#8b97a7",
  reflection:   "#b388ff",
  event:        "#34d399",
  decision:     "#4ade80",
};

export default function EventFeed() {
  const events = useWorld((s) => s.world?.events) ?? [];
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];

  return (
    <div className="panel feed">
      <div className="section">City feed</div>
      {activeCrises.length > 0 && (
        <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {activeCrises.map((name) => (
            <span
              key={name}
              style={{
                fontSize: 10, padding: "2px 7px", borderRadius: 999,
                background: "rgba(248,113,113,0.15)", color: "#f87171",
                border: "1px solid rgba(248,113,113,0.3)",
              }}
            >
              ⚠️ {name}
            </span>
          ))}
        </div>
      )}
      {events.length === 0 && (
        <div className="muted small">Waiting for the city to stir…</div>
      )}
      {[...events].reverse().map((e, i) => (
        <div key={i} className="feed-row">
          <span
            className="kind-icon"
            title={e.kind}
            style={{ color: KIND_COLOR[e.kind] ?? "#8b97a7" }}
          >
            {KIND_ICON[e.kind] ?? "·"}
          </span>
          <span className="small" style={{ color: KIND_COLOR[e.kind] ?? "inherit" }}>
            {e.text}
          </span>
        </div>
      ))}
    </div>
  );
}
