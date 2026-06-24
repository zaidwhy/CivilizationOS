import { useEffect, useRef, useState, useCallback } from "react";

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
  averted_fear: number;
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

function CouncilScorecard({ councils }: { councils: CouncilRecord[] }) {
  const INST_COLORS: Record<string, string> = {
    inst_gov: "#6ea8fe",
    inst_economy: "#fbbf24",
    inst_health: "#34d399",
    inst_media: "#f472b6",
    inst_police: "#fb923c",
  };

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 10, color: "#64748b", marginBottom: 6 }}>
        Council track record
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {councils.map((c) => {
          const color = INST_COLORS[c.institution_id] ?? "#94a3b8";
          const eff = c.effectiveness;
          const barColor = eff === null ? "#334155"
            : eff >= 65 ? "#4ade80"
            : eff >= 40 ? "#fbbf24"
            : "#f87171";
          const effLabel = eff === null
            ? (c.pending_snapshots > 0 ? "measuring…" : "no data")
            : `${eff}%`;

          const avertedPts = Math.round(c.averted_fear * 100);
          return (
            <div key={c.institution_id} style={{ display: "grid", gridTemplateColumns: "62px 1fr 46px", gap: 6, alignItems: "center" }}>
              <span style={{ fontSize: 10, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.name}
              </span>
              <div
                title={`${c.debates} debates · ${c.verdicts} verdicts · ${c.measured_verdicts} measured · avg fear delta ${c.avg_fear_delta !== null ? (c.avg_fear_delta > 0 ? "-" : "+") + Math.abs(Math.round((c.avg_fear_delta ?? 0) * 100)) + "%" : "n/a"} · averted ${avertedPts}% fear pts`}
                style={{ height: 5, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}
              >
                <div style={{
                  height: "100%", borderRadius: 999,
                  width: eff !== null ? `${eff}%` : "0%",
                  background: barColor,
                  transition: "width 0.5s, background 0.3s",
                }} />
              </div>
              <span style={{ fontSize: 9, color: barColor, textAlign: "right", whiteSpace: "nowrap" }}>
                {effLabel}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 9, color: "#1e3a5f", marginTop: 4 }}>
        effectiveness = fear reduction 60 ticks after verdict
      </div>
    </div>
  );
}

export default function StatsPanel() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [councils, setCouncils] = useState<CouncilRecord[]>([]);
  const [exporting, setExporting] = useState(false);

  const handleExport = useCallback(async () => {
    setExporting(true);
    try {
      const res = await fetch("/api/export");
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") ?? "";
      const match = disp.match(/filename=([^\s;]+)/);
      const filename = match ? match[1] : "civos_export.json";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* transient */ }
    finally { setExporting(false); }
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) setStats(await res.json());
      } catch { /* transient */ }
    };
    const fetchTrack = async () => {
      try {
        const res = await fetch("/api/track_record");
        if (res.ok) {
          const d = await res.json();
          setCouncils(d.councils ?? []);
        }
      } catch { /* transient */ }
    };
    fetchStats();
    fetchTrack();
    const id1 = setInterval(fetchStats, 5000);
    const id2 = setInterval(fetchTrack, 8000);
    return () => { clearInterval(id1); clearInterval(id2); };
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

      {councils.length > 0 && <CouncilScorecard councils={councils} />}

      {/* What-if summary */}
      {councils.some((c) => c.averted_fear > 0) && (() => {
        const totalAverted = councils.reduce((s, c) => s + c.averted_fear, 0);
        const totalVerdicts = councils.reduce((s, c) => s + c.verdicts, 0);
        return (
          <div style={{
            marginTop: 8, padding: "6px 8px",
            background: "rgba(52,211,153,0.06)",
            border: "1px solid rgba(52,211,153,0.12)",
            borderRadius: 5,
          }}>
            <div style={{ fontSize: 9, color: "#34d399" }}>What if no council verdicts?</div>
            <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
              City fear would be ~<span style={{ color: "#34d399" }}>{Math.round(totalAverted * 100)}pts</span> higher across {totalVerdicts} ruling{totalVerdicts !== 1 ? "s" : ""}
            </div>
          </div>
        );
      })()}

      {/* Export button */}
      <div style={{ marginTop: 10, display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={handleExport}
          disabled={exporting}
          title="Download full session as JSON"
          style={{
            fontSize: 10, padding: "4px 10px",
            background: "rgba(110,168,254,0.08)",
            border: "1px solid rgba(110,168,254,0.2)",
            borderRadius: 5, color: exporting ? "#334155" : "#6ea8fe",
            cursor: exporting ? "not-allowed" : "pointer",
          }}
        >
          {exporting ? "exporting…" : "⬇ Export session JSON"}
        </button>
      </div>

      <div style={{ fontSize: 9, color: "#334155", marginTop: 6, textAlign: "right" }}>
        tick {stats.tick}
      </div>
    </div>
  );
}
