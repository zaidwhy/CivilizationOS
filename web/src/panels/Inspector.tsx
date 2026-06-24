import { useEffect, useRef } from "react";
import { useWorld } from "../ws/store";

const KIND_COLOR: Record<string, string> = {
  observation: "#8b97a7",
  conversation: "#6ea8fe",
  reflection: "#b388ff",
  event: "#fbbf24",
  decision: "#fbbf24",
};

function FearSparkline({ history }: { history: [number, number][] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const W = 220, H = 28;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || history.length < 2) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, W, H);
    const fears = history.map(([, f]) => f);
    const maxF = Math.max(...fears, 0.01);
    const step = W / (history.length - 1);

    const toY = (f: number) => H - 4 - (f / maxF) * (H - 8);
    const toX = (i: number) => i * step;

    // Filled area
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "rgba(248,113,113,0.45)");
    grad.addColorStop(1, "rgba(248,113,113,0.04)");

    ctx.beginPath();
    ctx.moveTo(toX(0), H);
    ctx.lineTo(toX(0), toY(fears[0]));
    fears.forEach((f, i) => { if (i > 0) ctx.lineTo(toX(i), toY(f)); });
    ctx.lineTo(toX(fears.length - 1), H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(fears[0]));
    fears.forEach((f, i) => { if (i > 0) ctx.lineTo(toX(i), toY(f)); });
    ctx.strokeStyle = "#f87171";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Current dot
    const lastX = toX(fears.length - 1);
    const lastY = toY(fears[fears.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = "#fca5a5";
    ctx.fill();
  }, [history]);

  if (history.length < 3) return null;
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ fontSize: 9, color: "#475569", marginBottom: 2 }}>
        Fear history ({history.length} samples)
      </div>
      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        style={{ borderRadius: 3, background: "rgba(0,0,0,0.12)", display: "block" }}
      />
    </div>
  );
}

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
  const factions = useWorld((s) => s.world?.factions) ?? [];
  const myFaction = factions.find((f) => f.member_ids.includes(selectedId ?? ""));

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

      {myFaction && (
        <div style={{
          display: "flex", alignItems: "baseline", gap: 6,
          margin: "6px 0",
          padding: "5px 9px",
          background: "rgba(167,139,250,0.07)",
          border: "1px solid rgba(167,139,250,0.2)",
          borderRadius: 6,
          fontSize: 11,
        }}>
          <span style={{ color: "#a78bfa", whiteSpace: "nowrap" }}>🤝 {myFaction.name}</span>
          <span style={{ color: "#475569", fontSize: 10 }}>
            · {myFaction.member_names.filter((n) => n !== detail.name.split(" ")[0]).join(", ")}
          </span>
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
          <FearSparkline history={detail.fear_history ?? []} />
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
