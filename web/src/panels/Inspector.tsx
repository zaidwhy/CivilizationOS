import { useWorld } from "../ws/store";

const KIND_COLOR: Record<string, string> = {
  observation: "#8b97a7",
  conversation: "#6ea8fe",
  reflection: "#b388ff",
  event: "#fbbf24",
  decision: "#fbbf24",
};

const FEAR_LABEL = (pct: number) => {
  if (pct < 10) return null;
  if (pct < 30) return "uneasy";
  if (pct < 55) return "worried";
  if (pct < 75) return "afraid";
  return "terrified";
};

export default function Inspector() {
  const detail = useWorld((s) => s.detail);
  const selectedId = useWorld((s) => s.selectedId);
  const select = useWorld((s) => s.select);

  if (!selectedId) {
    return (
      <div className="panel hint">
        <p>Click a citizen on the city map to inspect their mind — memories, relationships, and current state.</p>
      </div>
    );
  }

  if (!detail) return <div className="panel" style={{ color: "var(--muted)", fontSize: 12 }}>Loading…</div>;

  const fearPct = Math.round((detail.fear ?? 0) * 100);
  const fearLabel = FEAR_LABEL(fearPct);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">{detail.name}</div>
          <div className="muted small">{detail.occupation} · {detail.traits}</div>
        </div>
        <button className="x" onClick={() => select(null)}>✕</button>
      </div>

      {detail.backstory && (
        <div style={{
          margin: "8px 0",
          padding: "7px 9px",
          background: "rgba(110,168,254,0.06)",
          border: "1px solid rgba(110,168,254,0.15)",
          borderRadius: 6,
          fontSize: 11,
          color: "#94a3b8",
          lineHeight: 1.5,
        }}>
          {detail.backstory}
        </div>
      )}

      <div className="now">{detail.action}</div>

      {fearLabel && (
        <div className="fear-bar">
          <div className="fear-label">
            ⚠ {fearLabel}{detail.active_crisis ? ` — ${detail.active_crisis}` : ""} ({fearPct}%)
          </div>
          <div className="fear-track">
            <div className="fear-fill" style={{ width: `${fearPct}%` }} />
          </div>
        </div>
      )}

      {detail.relationships.length > 0 && (
        <>
          <div className="section">Relationships</div>
          {detail.relationships.slice(0, 6).map((r) => (
            <div key={r.id} className="rel">
              <span style={{ fontSize: 12 }}>
                {r.affinity >= 0 ? "♥" : "⚡"} {r.name}
              </span>
              <div className="bar">
                <div
                  className="fill"
                  style={{
                    width: `${Math.abs(r.affinity) * 100}%`,
                    background: r.affinity >= 0 ? "var(--good)" : "var(--warn)",
                  }}
                />
              </div>
            </div>
          ))}
        </>
      )}

      <div className="section">Memory stream ({detail.memories.length})</div>
      <div className="memories">
        {detail.memories.length === 0 && <div className="muted small">No memories yet…</div>}
        {detail.memories.map((m, i) => (
          <div key={i} className="mem">
            <span className="dot" style={{ background: KIND_COLOR[m.kind] ?? "#8b97a7" }} />
            <div>
              <div className="small">{m.text}</div>
              <div className="muted xsmall">
                {m.kind} · importance {m.importance.toFixed(0)} · tick {m.tick}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
