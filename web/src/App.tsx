import { useEffect, useRef, useState } from "react";
import { connectWorldSocket, useWorld } from "./ws/store";
import CityStage from "./city/CityStage3D";
import Inspector from "./panels/Inspector";
import EventFeed from "./panels/EventFeed";
import CouncilChamber from "./panels/CouncilChamber";
import RelationshipGraph from "./panels/RelationshipGraph";
import Timeline from "./panels/Timeline";
import StatsPanel from "./panels/StatsPanel";
import Onboarding from "./components/Onboarding";
import Chronicle from "./panels/Chronicle";

// ---- Stability sparkline (topbar) ----
function StabilitySparkline() {
  const history = useWorld((s) => s.stabilityHistory);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const W = 80, H = 22;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || history.length < 2) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    const scores = history.map(([, s]) => s);
    const step = W / (scores.length - 1);
    const toY = (s: number) => H - 2 - (s / 100) * (H - 4);
    const toX = (i: number) => i * step;
    const last = scores[scores.length - 1];
    const color = last >= 60 ? "#4ade80" : last >= 35 ? "#fbbf24" : "#f87171";
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, color + "50");
    grad.addColorStop(1, color + "08");
    ctx.beginPath();
    ctx.moveTo(toX(0), H);
    ctx.lineTo(toX(0), toY(scores[0]));
    scores.forEach((s, i) => { if (i > 0) ctx.lineTo(toX(i), toY(s)); });
    ctx.lineTo(toX(scores.length - 1), H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(scores[0]));
    scores.forEach((s, i) => { if (i > 0) ctx.lineTo(toX(i), toY(s)); });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }, [history]);

  if (history.length < 3) return null;
  const last = history[history.length - 1][1];
  return (
    <canvas
      ref={canvasRef} width={W} height={H}
      style={{ borderRadius: 3, background: "rgba(0,0,0,0.2)", cursor: "default" }}
      title={`City stability over ${history.length * 5} ticks — current: ${last}`}
    />
  );
}

// ---- Toast notifications (overlay on city) ----
type ToastItem = { id: number; kind: "crisis" | "verdict" | "social"; text: string };
const TOAST_COLORS = { crisis: "#f87171", verdict: "#fbbf24", social: "#a78bfa" };
const TOAST_ICONS  = { crisis: "⚡",      verdict: "★",        social: "🤝" };

function ToastStack() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const seenTickRef = useRef(-1);

  useEffect(() => {
    return useWorld.subscribe((state) => {
      const events = state.world?.events;
      if (!events?.length) return;
      const maxTick = Math.max(...events.map(e => e.tick));
      if (maxTick <= seenTickRef.current) return;
      const fresh = events.filter(e => e.tick > seenTickRef.current);
      seenTickRef.current = maxTick;
      const interesting = fresh.filter(e =>
        e.kind === "emergent" ||
        (e.kind === "event" && /bloc|rivalry|dissolved/i.test(e.text)) ||
        (e.kind === "decision" && e.text.includes("VERDICT"))
      );
      if (!interesting.length) return;
      const now = Date.now();
      setToasts(prev => [
        ...prev,
        ...interesting.map((e, i) => ({
          id: now + i,
          kind: (e.kind === "emergent" ? "crisis" : e.kind === "decision" ? "verdict" : "social") as ToastItem["kind"],
          text: e.text.replace(/^[⚡★🤝💔⚠\s]+/, "").slice(0, 72),
        })),
      ].slice(-3));
    });
  }, []);

  useEffect(() => {
    if (!toasts.length) return;
    const id = setTimeout(() => setToasts(p => p.slice(1)), 5000);
    return () => clearTimeout(id);
  }, [toasts.length]);

  if (!toasts.length) return null;
  return (
    <div style={{
      position: "absolute", bottom: 14, left: 14, zIndex: 20,
      display: "flex", flexDirection: "column", gap: 5,
      pointerEvents: "none",
    }}>
      {toasts.map(t => (
        <div key={t.id} style={{
          padding: "8px 13px",
          background: `${TOAST_COLORS[t.kind]}14`,
          border: `1px solid ${TOAST_COLORS[t.kind]}50`,
          borderRadius: 8, fontSize: 11, color: "#e2e8f0",
          backdropFilter: "blur(6px)", maxWidth: 270, lineHeight: 1.45,
          animation: "toast-slide-in 0.3s ease-out",
        }}>
          <span style={{ color: TOAST_COLORS[t.kind], marginRight: 5 }}>{TOAST_ICONS[t.kind]}</span>
          {t.text}
        </div>
      ))}
    </div>
  );
}

// ---- Scenario quick-launch overlay ----
const QUICK_SCENARIOS = [
  { key: "pandemic",    emoji: "🦠", label: "Epidemic",   inst: "inst_health" },
  { key: "crime_wave",  emoji: "🚨", label: "Crime Wave", inst: "inst_police" },
  { key: "power_outage",emoji: "⚡", label: "Blackout",   inst: "inst_gov"    },
  { key: "drought",     emoji: "🌵", label: "Drought",    inst: "inst_economy"},
  { key: "cyberattack", emoji: "💻", label: "Cyberattack",inst: "inst_gov"    },
];

function ScenarioLauncher() {
  const [open, setOpen] = useState(false);
  const [firing, setFiring] = useState<string | null>(null);

  async function fire(key: string, inst: string) {
    setFiring(key);
    try {
      await fetch("/api/crisis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "", institution_id: inst, template_key: key }),
      });
    } catch { /* ignore */ }
    finally { setFiring(null); setOpen(false); }
  }

  return (
    <div style={{
      position: "absolute", top: 10, right: 10, zIndex: 20,
      display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5,
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: open ? "rgba(124,58,237,0.9)" : "rgba(124,58,237,0.75)",
          color: "#fff", border: "1px solid rgba(167,139,250,0.45)",
          borderRadius: 6, padding: "4px 12px", fontSize: 12,
          cursor: "pointer", backdropFilter: "blur(6px)", fontWeight: 600,
        }}
      >
        {open ? "✕" : "⚡ Scenarios"}
      </button>
      {open && (
        <div style={{
          background: "rgba(11,14,20,0.88)", backdropFilter: "blur(10px)",
          border: "1px solid var(--line)", borderRadius: 8, padding: 7,
          display: "flex", flexDirection: "column", gap: 4, minWidth: 148,
        }}>
          {QUICK_SCENARIOS.map(s => (
            <button
              key={s.key}
              onClick={() => fire(s.key, s.inst)}
              disabled={!!firing}
              style={{
                background: firing === s.key ? "rgba(124,58,237,0.45)" : "rgba(255,255,255,0.04)",
                color: "#e2e8f0", border: "1px solid var(--line)",
                borderRadius: 5, padding: "5px 10px", fontSize: 12,
                cursor: firing ? "not-allowed" : "pointer",
                textAlign: "left", display: "flex", alignItems: "center", gap: 7,
                transition: "background 0.15s",
              }}
            >
              <span style={{ fontSize: 14 }}>{s.emoji}</span>
              <span>{firing === s.key ? "Injecting…" : s.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const PHASE_LABEL: Record<string, string> = {
  night: "🌙 Night",
  morning: "🌅 Morning",
  work: "🏙️ Work",
  evening: "🌆 Evening",
};

function SpeedControl() {
  const health = useWorld((s) => s.health);
  const [local, setLocal] = useState(1.0);

  useEffect(() => {
    if (health?.tick_interval != null) setLocal(health.tick_interval);
  }, [health?.tick_interval]);

  async function changeSpeed(v: number) {
    setLocal(v);
    try {
      await fetch("/api/speed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seconds_per_tick: v }),
      });
    } catch { /* ignore */ }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 11, color: "#64748b" }}>speed</span>
      <input
        type="range" min={0.1} max={3} step={0.1}
        value={local}
        onChange={(e) => changeSpeed(parseFloat(e.target.value))}
        style={{ width: 70, accentColor: "#6ea8fe", cursor: "pointer" }}
        title={`${local.toFixed(1)}s / tick`}
      />
      <span className="pill" style={{ fontSize: 10, minWidth: 36, textAlign: "center" }}>
        {local.toFixed(1)}s
      </span>
    </div>
  );
}

function TensionMeter() {
  const pressure = useWorld((s) => s.world?.fear_pressure ?? 0);
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];
  if (pressure <= 0.05) return null;

  const pct = Math.round(pressure * 100);
  const color = pressure >= 0.75 ? "#f87171" : pressure >= 0.40 ? "#fb923c" : "#fbbf24";
  const label = pressure >= 0.99
    ? "⚡ ERUPTING"
    : activeCrises.length > 0
    ? `⚡ COMPOUND ${pct}%`
    : `⚡ TENSION ${pct}%`;

  return (
    <span
      className="pill"
      title={`Fear has been critically high for ${pct}% of the auto-crisis threshold. A new crisis will erupt if it stays this high.`}
      style={{
        color,
        borderColor: color,
        cursor: "default",
        animation: pressure >= 0.85 ? "crisis-pulse 1s ease-in-out infinite" : undefined,
      }}
    >
      {label}
    </span>
  );
}

function StabilityBadge() {
  const citizens = useWorld((s) => s.world?.citizens) ?? [];
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];

  if (citizens.length === 0) return null;

  const avgFear = citizens.reduce((sum, c) => sum + (c.fear ?? 0), 0) / citizens.length;
  const score = Math.max(0, Math.min(100, Math.round(100 - avgFear * 65 - activeCrises.length * 12)));

  const [label, color] =
    score >= 80 ? ["THRIVING", "#4ade80"]
    : score >= 60 ? ["STABLE", "#a3e635"]
    : score >= 40 ? ["TENSE", "#fbbf24"]
    : score >= 20 ? ["UNSTABLE", "#fb923c"]
    : ["CRITICAL", "#f87171"];

  return (
    <span
      className="pill"
      title={`City stability ${score}/100 — avg fear ${Math.round(avgFear * 100)}%, ${activeCrises.length} active crisis`}
      style={{ color, borderColor: color, cursor: "default", fontWeight: 700 }}
    >
      ◈ {label} {score}
    </span>
  );
}

function SpendCounter() {
  const health = useWorld((s) => s.health);
  if (!health) return <span className="pill">brains · loading…</span>;

  const spent = health.tier2_spent_usd;
  const budget = health.tier2_budget_usd;
  const pct = Math.min(100, (spent / budget) * 100);
  const color = pct > 80 ? "#f87171" : pct > 50 ? "#fbbf24" : "#4ade80";

  return (
    <>
      {health.council_model && (
        <span
          className="pill"
          title={`Fine-tuned council model active: ${health.council_model}`}
          style={{ color: "#a78bfa", borderColor: "#a78bfa", cursor: "default" }}
        >
          🧠 {health.council_model}
        </span>
      )}
      <span
        className="pill"
        title={`$${spent.toFixed(4)} of $${budget} Claude budget used (${pct.toFixed(1)}%)`}
        style={{ color, borderColor: color, cursor: "default" }}
      >
        {health.premium_mode ? "⚡ premium" : "⚙ free"} · ${spent.toFixed(3)}
      </span>
    </>
  );
}

export default function App() {
  const conn = useWorld((s) => s.conn);
  const world = useWorld((s) => s.world);
  const activeCrises = useWorld((s) => s.world?.active_crises) ?? [];

  useEffect(() => connectWorldSocket(), []);

  return (
    <div className="app">
      <Onboarding />
      <header className="topbar">
        <h1>CIVILIZATION&nbsp;OS</h1>
        <span className={`pill ${conn === "open" ? "live" : "off"}`}>
          {conn === "open" ? "● live" : conn}
        </span>
        {world && (
          <>
            <span className="pill">{world.clock}</span>
            <span className="pill">{PHASE_LABEL[world.phase] ?? world.phase}</span>
            <span className="pill">{world.citizens.length} citizens</span>
          </>
        )}
        {activeCrises.map((name) => (
          <span key={name} className="pill crisis-pill">
            ⚠ {name}
          </span>
        ))}
        <TensionMeter />
        <span className="grow" />
        <StabilitySparkline />
        <StabilityBadge />
        <SpeedControl />
        <SpendCounter />
      </header>

      <main className="layout">
        <div className="city">
          <CityStage />
          <ToastStack />
          <ScenarioLauncher />
        </div>
        <aside className="sidebar">
          <Inspector />
          <RelationshipGraph />
          <EventFeed />
          <CouncilChamber />
          <Timeline />
          <Chronicle />
          <StatsPanel />
        </aside>
      </main>
    </div>
  );
}
