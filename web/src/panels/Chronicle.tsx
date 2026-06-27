import { useEffect, useState } from "react";
import { useWorld } from "../ws/store";

type ChronicleData = {
  text: string;
  tick: number;
  avg_fear: number;
  active_crises: string[];
};

export default function Chronicle() {
  const [data, setData] = useState<ChronicleData | null>(null);
  const [loading, setLoading] = useState(false);
  const factions = useWorld((s) => s.world?.factions) ?? [];

  const fetchChronicle = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await fetch("/api/chronicle");
      if (res.ok) setData(await res.json());
    } catch { /* transient */ }
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchChronicle();
    const id = setInterval(fetchChronicle, 75_000);
    return () => clearInterval(id);
  }, []);

  if (!data) return null;

  const fearPct = Math.round(data.avg_fear * 100);
  const fearColor = fearPct >= 60 ? "#f87171" : fearPct >= 35 ? "#fbbf24" : "#4ade80";
  const dayNum = Math.floor(data.tick / 96) + 1;

  return (
    <div className="panel" style={{ borderTop: "1px solid var(--line)" }}>
      {/* Masthead */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 13, color: "#60a5fa", letterSpacing: 1.5 }}>
            📰 CITY CHRONICLE
          </h3>
          <div style={{ fontSize: 9, color: "#334155", marginTop: 2, letterSpacing: 0.5 }}>
            DISPATCH · DAY {dayNum} · TICK {data.tick} · CIVOSVILLE BUREAU
          </div>
        </div>
        <button
          onClick={fetchChronicle}
          disabled={loading}
          style={{
            background: "none", border: "1px solid var(--line)", borderRadius: 4,
            color: loading ? "#334155" : "#475569", fontSize: 12,
            cursor: loading ? "not-allowed" : "pointer", padding: "1px 6px",
          }}
        >
          {loading ? "…" : "↻"}
        </button>
      </div>

      {/* Divider rule */}
      <div style={{
        height: 1,
        background: "linear-gradient(90deg, #1e3a5f 0%, #334155 50%, transparent 100%)",
        marginBottom: 10,
      }} />

      {/* Dispatch body */}
      <div style={{
        fontSize: 12.5,
        color: "#a8b8cc",
        lineHeight: 1.8,
        fontStyle: "italic",
        borderLeft: "2px solid #1e3a5f",
        paddingLeft: 10,
        marginBottom: 10,
        animation: "fade-in 0.3s ease-out",
      }}>
        {data.text}
      </div>

      {/* Fear bar */}
      <div style={{ marginBottom: 8 }}>
        <div style={{
          display: "flex", justifyContent: "space-between",
          fontSize: 9, color: "#475569", marginBottom: 3,
        }}>
          <span style={{ letterSpacing: 0.4 }}>CITY FEAR LEVEL</span>
          <span style={{ color: fearColor, fontWeight: 600 }}>{fearPct}%</span>
        </div>
        <div style={{ height: 3, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}>
          <div style={{
            height: "100%", width: `${fearPct}%`,
            background: `linear-gradient(90deg, #4ade80, ${fearColor})`,
            transition: "width 0.6s ease",
            borderRadius: 999,
          }} />
        </div>
      </div>

      {/* Active crises */}
      {data.active_crises.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
          {data.active_crises.map(c => (
            <span key={c} style={{
              fontSize: 9, padding: "1px 6px", borderRadius: 999,
              background: "rgba(248,113,113,0.1)", color: "#f87171",
              border: "1px solid rgba(248,113,113,0.25)",
            }}>
              ⚠ {c}
            </span>
          ))}
        </div>
      )}

      {/* Active faction blocs */}
      {factions.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {factions.map(f => (
            <span key={f.id} style={{
              fontSize: 9, padding: "1px 6px", borderRadius: 999,
              background: "rgba(167,139,250,0.08)", color: "#a78bfa",
              border: "1px solid rgba(167,139,250,0.25)",
            }}>
              🤝 {f.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
