import { useEffect, useRef, useState } from "react";

type StatsData = {
  tick: number;
  avg_fear: number;
  fear_buckets: number[];
  memory_counts: Record<string, number>;
  total_debates: number;
  active_crises: number;
  causal_events: number;
};

type CouncilRecord = {
  institution_id: string;
  name: string;
  debates: number;
  verdicts: number;
  avg_fear_delta: number | null;
  effectiveness: number | null;
  measured_verdicts: number;
  pending_snapshots: number;
};

const BUCKET_LABELS = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"];
const BUCKET_COLORS = ["#4ade80", "#a3e635", "#fbbf24", "#fb923c", "#f87171"];

function FearHistogram({ buckets }: { buckets: number[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const max = Math.max(...buckets, 1);
  const W = 220;
  const H = 60;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, W, H);
    const barW = W / buckets.length;
    const padX = 4;

    buckets.forEach((v, i) => {
      const barH = (v / max) * (H - 14);
      const x = i * barW + padX / 2;
      const y = H - barH - 12;

      ctx.fillStyle = BUCKET_COLORS[i];
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.roundRect(x, y, barW - padX, barH, 2);
      ctx.fill();
      ctx.globalAlpha = 1;

      // count label
      if (v > 0) {
        ctx.font = "9px monospace";
        ctx.fillStyle = BUCKET_COLORS[i];
        ctx.textAlign = "center";
        ctx.fillText(String(v), x + (barW - padX) / 2, y - 2);
      }

      // x-axis label
      ctx.font = "8px monospace";
      ctx.fillStyle = "#475569";
      ctx.textAlign = "center";
      ctx.fillText(BUCKET_LABELS[i].split("–")[0], x + (barW - padX) / 2, H - 1);
    });
  }, [buckets, max]);

  return (
    <canvas
      ref={canvasRef}
      width={W}
      height={H}
      style={{ borderRadius: 4, background: "rgba(0,0,0,0.15)", display: "block" }}
    />
  );
}

export default function StatsPanel() {
  const [stats, setStats] = useState<StatsData | null>(null);

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) setStats(await res.json());
      } catch { /* transient */ }
    };
    fetch_();
    const id = setInterval(fetch_, 5000);
    return () => clearInterval(id);
  }, []);

  if (!stats) return null;

  const sortedMembers = Object.entries(stats.memory_counts).sort((a, b) => b[1] - a[1]);
  const fearPct = Math.round(stats.avg_fear * 100);

  return (
    <div className="panel" style={{ borderTop: "1px solid var(--line)" }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 13, color: "#a78bfa", letterSpacing: 1 }}>
        📊 CITY STATS
      </h3>

      {/* Fear histogram */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4 }}>
          Fear distribution · avg {fearPct}%
        </div>
        <FearHistogram buckets={stats.fear_buckets} />
      </div>

      {/* Session counters */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
        gap: 6, marginBottom: 10,
      }}>
        {[
          { label: "debates", value: stats.total_debates, color: "#fbbf24" },
          { label: "causal nodes", value: stats.causal_events, color: "#34d399" },
          { label: "active crises", value: stats.active_crises, color: "#f87171" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: "rgba(0,0,0,0.2)",
            borderRadius: 6,
            padding: "6px 8px",
            textAlign: "center",
            border: `1px solid ${color}22`,
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: 9, color: "#475569", marginTop: 1 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Memory league table */}
      <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4 }}>
        Memories per citizen
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {sortedMembers.map(([name, count]) => {
          const maxCount = sortedMembers[0][1] || 1;
          return (
            <div key={name} style={{ display: "grid", gridTemplateColumns: "70px 1fr 22px", gap: 5, alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {name.split(" ")[0]}
              </span>
              <div style={{ height: 4, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}>
                <div style={{
                  height: "100%", borderRadius: 999,
                  width: `${(count / maxCount) * 100}%`,
                  background: "#a78bfa",
                  transition: "width 0.4s",
                }} />
              </div>
              <span style={{ fontSize: 9, color: "#64748b", textAlign: "right" }}>{count}</span>
            </div>
          );
        })}
      </div>

      <div style={{ fontSize: 9, color: "#334155", marginTop: 8, textAlign: "right" }}>
        tick {stats.tick}
      </div>
    </div>
  );
}
