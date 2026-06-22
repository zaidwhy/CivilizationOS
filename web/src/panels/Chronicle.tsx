import { useEffect, useState } from "react";

type ChronicleData = {
  text: string;
  tick: number;
  avg_fear: number;
  active_crises: string[];
};

export default function Chronicle() {
  const [data, setData] = useState<ChronicleData | null>(null);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="panel" style={{ borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "#60a5fa", letterSpacing: 1 }}>
          📰 CITY CHRONICLE
        </h3>
        <button
          onClick={fetchChronicle}
          disabled={loading}
          title="Refresh dispatch"
          style={{
            background: "none", border: "1px solid var(--line)", borderRadius: 4,
            color: loading ? "#334155" : "#475569", fontSize: 12,
            cursor: loading ? "not-allowed" : "pointer", padding: "1px 6px",
          }}
        >
          {loading ? "…" : "↻"}
        </button>
      </div>

      <div style={{
        fontSize: 12,
        color: "#94a3b8",
        lineHeight: 1.75,
        fontStyle: "italic",
        borderLeft: "2px solid #1e3a5f",
        paddingLeft: 10,
      }}>
        {data.text}
      </div>

      <div style={{
        fontSize: 9, color: "#334155",
        marginTop: 8, textAlign: "right",
        display: "flex", justifyContent: "space-between",
      }}>
        <span style={{ color: "#1e3a5f" }}>
          {data.active_crises.length > 0 ? `⚠ ${data.active_crises.join(", ")}` : "no active crises"}
        </span>
        <span>tick {data.tick} · fear {Math.round(data.avg_fear * 100)}%</span>
      </div>
    </div>
  );
}
