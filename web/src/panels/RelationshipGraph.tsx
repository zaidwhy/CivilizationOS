import { useEffect, useRef, useState } from "react";
import { useWorld, Faction } from "../ws/store";

const W = 260;
const H = 210;
const FACTION_COLORS = ["#a78bfa", "#f472b6", "#34d399", "#fb923c", "#60a5fa"] as const;
const R = 7;
const REPULSION = 1400;
const SPRING_STRENGTH = 0.05;
const IDEAL_DIST_POS = 55;
const IDEAL_DIST_NEG = 95;
const GRAVITY = 0.004;
const DAMPING = 0.82;

type PhysNode = { id: string; x: number; y: number; vx: number; vy: number };
type GraphNode = { id: string; name: string; occupation: string; fear: number };
type GraphEdge = { source: string; target: string; weight: number; positive: boolean };
type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

type TooltipData = {
  name: string;
  occupation: string;
  fear: number;
  faction?: string;
  bonds: { name: string; weight: number; positive: boolean }[];
  x: number;
  y: number;
};

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
  const factions = useWorld((s) => s.world?.factions) ?? ([] as Faction[]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  // Refs for RAF loop — avoids stale closure / restart on every render
  const citizensRef = useRef(citizens);
  const selectedIdRef = useRef(selectedId);
  const graphRef = useRef(graph);
  const factionsRef = useRef(factions);
  const physRef = useRef<Map<string, PhysNode>>(new Map());
  const rafRef = useRef<number>(0);

  useEffect(() => { citizensRef.current = citizens; }, [citizens]);
  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);
  useEffect(() => { graphRef.current = graph; }, [graph]);
  useEffect(() => { factionsRef.current = factions; }, [factions]);

  // Poll /api/graph every 6 s
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

  // Single RAF loop — runs once on mount, reads everything from refs
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function physicsStep() {
      const cs = citizensRef.current;
      if (!cs) return;
      const phys = physRef.current;

      const citizenIds = new Set(cs.map((c) => c.id));
      cs.forEach((c, i) => {
        if (!phys.has(c.id)) {
          const angle = (2 * Math.PI * i) / cs.length - Math.PI / 2;
          phys.set(c.id, {
            id: c.id,
            x: W / 2 + (Math.min(W, H) / 2 - R - 12) * Math.cos(angle),
            y: H / 2 + (Math.min(W, H) / 2 - R - 12) * Math.sin(angle),
            vx: 0,
            vy: 0,
          });
        }
      });
      for (const id of phys.keys()) {
        if (!citizenIds.has(id)) phys.delete(id);
      }

      const nodes = [...phys.values()];
      const edges = graphRef.current?.edges ?? [];

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const dist = Math.max(Math.hypot(dx, dy), 1);
          const f = REPULSION / (dist * dist);
          const fx = (dx / dist) * f, fy = (dy / dist) * f;
          a.vx += fx; a.vy += fy;
          b.vx -= fx; b.vy -= fy;
        }
      }

      for (const edge of edges) {
        const a = phys.get(edge.source), b = phys.get(edge.target);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(Math.hypot(dx, dy), 1);
        const ideal = edge.positive ? IDEAL_DIST_POS : IDEAL_DIST_NEG;
        const spring = SPRING_STRENGTH * Math.abs(edge.weight);
        const f = spring * (dist - ideal);
        const fx = (dx / dist) * f, fy = (dy / dist) * f;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }

      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * GRAVITY;
        n.vy += (H / 2 - n.y) * GRAVITY;
        n.vx *= DAMPING;
        n.vy *= DAMPING;
        n.x = Math.max(R + 5, Math.min(W - R - 5, n.x + n.vx));
        n.y = Math.max(R + 10, Math.min(H - R - 12, n.y + n.vy));
      }
    }

    function draw() {
      const c2d = canvasRef.current;
      if (!c2d) return;
      const ctx = c2d.getContext("2d");
      if (!ctx) return;
      const cs = citizensRef.current;
      const selId = selectedIdRef.current;
      const edges = graphRef.current?.edges ?? [];
      const hasGraph = graphRef.current !== null;
      const phys = physRef.current;

      ctx.clearRect(0, 0, W, H);

      if (hasGraph && edges.length > 0) {
        for (const edge of edges) {
          const pa = phys.get(edge.source), pb = phys.get(edge.target);
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
      } else if (!hasGraph && cs) {
        cs.forEach((a) => {
          cs.forEach((b) => {
            if (a.id >= b.id) return;
            if (a.location_id && a.location_id === b.location_id && !a.location_id.startsWith("home_")) {
              const pa = phys.get(a.id), pb = phys.get(b.id);
              if (!pa || !pb) return;
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

      if (cs) {
        cs.forEach((c) => {
          const p = phys.get(c.id);
          if (!p) return;
          const isSel = c.id === selId;
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
      }
    }

    function frame() {
      physicsStep();
      draw();
      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []); // intentionally empty — loop runs once and reads from refs

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const cs = citizensRef.current;
    if (!cs) return;
    for (const c of cs) {
      const p = physRef.current.get(c.id);
      if (p && Math.hypot(mx - p.x, my - p.y) <= R + 4) {
        select(c.id);
        return;
      }
    }
    select(null);
  }

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const cs = citizensRef.current;
    const g = graphRef.current;
    if (!cs) { setTooltip(null); return; }

    let hoveredId: string | null = null;
    for (const c of cs) {
      const p = physRef.current.get(c.id);
      if (p && Math.hypot(mx - p.x, my - p.y) <= R + 6) {
        hoveredId = c.id;
        break;
      }
    }

    if (!hoveredId) { setTooltip(null); return; }

    const citizen = cs.find((c) => c.id === hoveredId);
    if (!citizen) { setTooltip(null); return; }

    const bonds: TooltipData["bonds"] = [];
    if (g?.edges) {
      for (const edge of g.edges) {
        const otherId = edge.source === hoveredId ? edge.target
          : edge.target === hoveredId ? edge.source
          : null;
        if (!otherId) continue;
        const other = cs.find((c) => c.id === otherId);
        if (other) bonds.push({ name: other.name.split(" ")[0], weight: Math.abs(edge.weight), positive: edge.positive });
      }
      bonds.sort((a, b) => b.weight - a.weight);
    }

    const p = physRef.current.get(hoveredId)!;
    setTooltip({
      name: citizen.name,
      occupation: citizen.occupation,
      fear: citizen.fear,
      bonds: bonds.slice(0, 3),
      x: p.x,
      y: p.y,
    });
  }

  const edgeCount = graph?.edges?.length ?? 0;

  // Flip tooltip to left side if node is in the right half of the canvas
  const tipLeft = tooltip ? (tooltip.x > W / 2 ? tooltip.x - 148 : tooltip.x + 14) : 0;
  const tipTop  = tooltip ? Math.max(0, tooltip.y - 14) : 0;

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
      <div style={{ position: "relative", display: "inline-block" }}>
        <canvas
          ref={canvasRef}
          width={W}
          height={H}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
          style={{ cursor: "pointer", borderRadius: 6, background: "rgba(0,0,0,0.2)", display: "block" }}
        />
        {tooltip && (
          <div style={{
            position: "absolute",
            left: tipLeft,
            top: tipTop,
            background: "#0f172a",
            border: "1px solid #334155",
            borderRadius: 7,
            padding: "7px 10px",
            fontSize: 11,
            color: "#cbd5e1",
            pointerEvents: "none",
            zIndex: 20,
            minWidth: 130,
            maxWidth: 150,
            boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
          }}>
            <div style={{ fontWeight: 700, color: "#f1f5f9", marginBottom: 1, fontSize: 12 }}>
              {tooltip.name}
            </div>
            <div style={{ color: "#64748b", marginBottom: 5, fontSize: 10 }}>
              {tooltip.occupation}
            </div>
            <div style={{ color: fearColor(tooltip.fear), marginBottom: tooltip.bonds.length ? 5 : 0, fontSize: 11 }}>
              fear&nbsp;{Math.round(tooltip.fear * 100)}%
            </div>
            {tooltip.bonds.map((b) => (
              <div key={b.name} style={{
                display: "flex", justifyContent: "space-between",
                color: b.positive ? "#4ade80" : "#f87171",
                fontSize: 10, marginTop: 2,
              }}>
                <span>{b.positive ? "♥" : "⚡"} {b.name}</span>
                <span>{Math.round(b.weight * 100)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
