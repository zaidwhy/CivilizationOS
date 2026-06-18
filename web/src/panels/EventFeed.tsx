import { useWorld } from "../ws/store";

export default function EventFeed() {
  // Select the stable reference; default outside the selector so zustand's
  // identity check doesn't see a new [] every render (that loops forever).
  const events = useWorld((s) => s.world?.events) ?? [];
  return (
    <div className="panel feed">
      <div className="section">City feed</div>
      {events.length === 0 && <div className="muted small">Waiting for the city to stir…</div>}
      {[...events].reverse().map((e, i) => (
        <div key={i} className="feed-row">
          <span className="kind">{e.kind}</span>
          <span className="small">{e.text}</span>
        </div>
      ))}
    </div>
  );
}
