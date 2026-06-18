import { useWorld } from "../ws/store";

const KIND_COLOR: Record<string, string> = {
  observation: "#8b97a7",
  conversation: "#6ea8fe",
  reflection: "#b388ff",
  event: "#fbbf24",
};

export default function Inspector() {
  const detail = useWorld((s) => s.detail);
  const selectedId = useWorld((s) => s.selectedId);
  const select = useWorld((s) => s.select);

  if (!selectedId) {
    return (
      <div className="panel hint">
        <p>Click a citizen to inspect their mind — memories, relationships, and what they’re doing.</p>
      </div>
    );
  }

  if (!detail) return <div className="panel">Loading…</div>;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">{detail.name}</div>
          <div className="muted small">{detail.occupation} · {detail.traits}</div>
        </div>
        <button className="x" onClick={() => select(null)}>✕</button>
      </div>

      <div className="now">{detail.action}</div>

      {detail.relationships.length > 0 && (
        <>
          <div className="section">Relationships</div>
          {detail.relationships.slice(0, 5).map((r) => (
            <div key={r.id} className="rel">
              <span>{r.name}</span>
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

      <div className="section">Memory stream</div>
      <div className="memories">
        {detail.memories.length === 0 && <div className="muted small">No memories yet…</div>}
        {detail.memories.map((m, i) => (
          <div key={i} className="mem">
            <span className="dot" style={{ background: KIND_COLOR[m.kind] ?? "#8b97a7" }} />
            <div>
              <div className="small">{m.text}</div>
              <div className="muted xsmall">{m.kind} · importance {m.importance}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
