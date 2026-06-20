import { useEffect, useRef, useState } from "react";
import { useWorld } from "../ws/store";

const W = 260;
const H = 200;
const R = 7;

type GraphNode = { id: string; name: string; occupation: string; fear: number };
type GraphEdge = { source: string; target: string; weight: number; positive: boolean };
type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

function fearColor(fear: number): string {
  const r = Math.round(59 + fear * (239 - 59));
  const g = Math.round(130 - fear * 100);
  const b = Math.round(246 - fear * 210);
  return `rgb(${r},${g},${b})`;
}

export default function RelationshipGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const citizens = useWorld((s) => s.world?.citizens);
  const selectedId = useWorld((s) => s.selectedId);
  const select = useWorld((s) => s.select);
  const [graph, setGraph] = useState<GraphData | null>(null);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const res = await fetch("/api/graph");
        if (res.ok) setGraph(await res.json());
      } catch { /* transient */ }
    };
    fetchGraph();
    const id = setInterval(fetchGraph, 6000);
    return () => clearInterval(id);
  }, []);

  // Layout: fixed circle based on world citizens order
  const positions: Record<string, { x: number; y: number }> = {};
  if (citizens) {
    const cx = W / 2, cy = H / 2, rad = Math.min(W, H) / 2 - R - 10;
    citizens.forEach((c, i) => {
      const angle = (2 * Math.PI * i) / citizens.length - Math.PI / 2;
      positions[c.id] = {
        x: cx + rad * Math.cos(angle),
        y: cy + rad * Math.sin(angle),
      };
    });
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !citizens) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, W, H);

    // Draw affinity edges from /api/graph
    if (graph?.edges) {
      for (const edge of graph.edges) {
        const pa = positions[edge.source];
        const pb = positions[edge.target];
        if (!pa || !pb) continue;
        const alpha = Math.min(0.9, Math.abs(edge.weight) * 1.5);
        const thickness = Math.max(0.5, Math.abs(edge.weight) * 3);
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.strokeStyle = edge.positive
          ? `rgba(74,222,128,${alpha})`
          : `rgba(248,113,113,${alpha})`;
        ctx.lineWidth = thickness;
        ctx.stroke();
      }
    } else {
      // Fallback: faint co-location lines while graph loads
      citizens.forEach((a) => {
        citizens.forEach((b) => {
          if (a.id >= b.id) return;
          if (a.location_id && a.location_id === b.location_id && !a.location_id.startsWith("home_")) {
            const pa = positions[a.id];
            const pb = positions[b.id];
            ctx.beginPath();
            ctx.moveTo(pa.x, pa.y);
            ctx.lineTo(pb.x, pb.y);
            ctx.strokeStyle = "rgba(148,163,184,0.2)";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });
      });
    }

    // Draw nodes
    citizens.forEach((c) => {
      const p = positions[c.id];
      const isSel = c.id === selectedId;
      ctx.beginPath();
      ctx.arc(p.x, p.y, isSel ? R + 2 : R, 0, 2 * Math.PI);
      ctx.fillStyle = fearColor(c.fear ?? 0);
      ctx.fill();
      if (isSel) {
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.font = "8px monospace";
      ctx.fillStyle = "#94a3b8";
      ctx.textAlign = "center";
      ctx.fillText(c.name.split(" ")[0], p.x, p.y + R + 9);
    });
  }, [citizens, selectedId, graph]);

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!citizens) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const c of citizens) {
      const p = positions[c.id];
      if (Math.hypot(mx - p.x, my - p.y) <= R + 4) {
        select(c.id);
        return;
      }
    }
    select(null);
  }

  const edgeCount = graph?.edges?.length ?? 0;

  return (
    <div className="panel">
      <h3 style={{ margin: "0 0 6px", fontSize: 13, color: "#60a5fa", letterSpacing: 1 }}>
        🕸 SOCIAL GRAPH
      </h3>
      <div style={{ fontSize: 10, color: "#64748b", marginBottom: 6, display: "flex", gap: 10 }}>
        <span>Node: <span style={{ color: "#3b82f6" }}>calm</span> → <span style={{ color: "#ef4444" }}>fear</span></span>
        <span>Edge: <span style={{ color: "#4ade80" }}>trust</span> · <span style={{ color: "#f87171" }}>tension</span></span>
        {edgeCount > 0 && <span style={{ marginLeft: "auto" }}>{edgeCount} bonds</span>}
      </div>
      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        onClick={handleClick}
        style={{ cursor: "pointer", borderRadius: 6, background: "rgba(0,0,0,0.2)" }}
      />
    </div>
  );
}
