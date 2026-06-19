import { useEffect, useRef } from "react";
import { useWorld } from "../ws/store";

const W = 260;
const H = 180;
const R = 7;

function fearColor(fear: number): string {
  // 0 → cool blue, 1 → hot red
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

  // Layout citizens in a circle
  const positions: Record<string, { x: number; y: number }> = {};
  if (citizens) {
    const cx = W / 2, cy = H / 2, rad = Math.min(W, H) / 2 - R - 8;
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

    // Draw edges (we don't have relationship data here without fetching detail,
    // so draw proximity lines based on same location)
    citizens.forEach((a) => {
      citizens.forEach((b) => {
        if (a.id >= b.id) return;
        if (a.location_id && a.location_id === b.location_id && !a.location_id.startsWith("home_")) {
          const pa = positions[a.id];
          const pb = positions[b.id];
          ctx.beginPath();
          ctx.moveTo(pa.x, pa.y);
          ctx.lineTo(pb.x, pb.y);
          ctx.strokeStyle = "rgba(148,163,184,0.25)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      });
    });

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
      // Name label
      ctx.font = "8px monospace";
      ctx.fillStyle = "#94a3b8";
      ctx.textAlign = "center";
      ctx.fillText(c.name.split(" ")[0], p.x, p.y + R + 9);
    });
  }, [citizens, selectedId]);

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

  return (
    <div className="panel">
      <h3 style={{ margin: "0 0 8px", fontSize: 13, color: "#60a5fa", letterSpacing: 1 }}>
        🕸 SOCIAL GRAPH
      </h3>
      <div style={{ fontSize: 10, color: "#64748b", marginBottom: 6 }}>
        Node color: <span style={{ color: "#3b82f6" }}>calm</span> → <span style={{ color: "#ef4444" }}>fear</span> · Lines = co-located
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
