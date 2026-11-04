import { useEffect, useRef, useState } from "react";
import { connectWorldSocket, useWorld } from "./ws/store";
import CityStage from "./city/CityStage3D";
import Narrator from "./city/Narrator";
import Inspector from "./panels/Inspector";
import EventFeed from "./panels/EventFeed";
import CouncilChamber from "./panels/CouncilChamber";
import RelationshipGraph from "./panels/RelationshipGraph";
import Timeline from "./panels/Timeline";
import StatsPanel from "./panels/StatsPanel";
import Chronicle from "./panels/Chronicle";
import { API_ROOT } from "./config";

// ---- Stability sparkline (details drawer) ----
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
    grad.addColorStop(0, color + "2e");
    grad.addColorStop(1, color + "05");
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
      title={`City stability over ${history.length * 5} ticks - current: ${last}`}
    />
  );
}

// ---- Crisis launcher (top right of the city) ----
const QUICK_SCENARIOS = [
  { key: "pandemic",     label: "Epidemic",    inst: "inst_health" },
  { key: "crime_wave",   label: "Crime wave",  inst: "inst_police" },
  { key: "power_outage", label: "Blackout",    inst: "inst_gov" },
  { key: "drought",      label: "Drought",     inst: "inst_economy" },
  { key: "cyberattack",  label: "Cyberattack", inst: "inst_gov" },
];

function ScenarioLauncher() {
  const [open, setOpen] = useState(false);
  const [firing, setFiring] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!note) return;
    const id = setTimeout(() => setNote(null), 6000);
    return () => clearTimeout(id);
  }, [note]);

  async function fire(key: string, inst: string) {
    setFiring(key);
    try {
      const res = await fetch(`${API_ROOT}/crisis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "", institution_id: inst, template_key: key }),
      });
      if (res.status === 429) {
        const body = await res.json().catch(() => null);
        setNote(typeof body?.detail === "string" ? body.detail : "Crises are rate-limited on the shared demo. Try again in a moment.");
      } else if (!res.ok) {
        setNote("The city could not start that crisis. Is the server awake?");
      } else {
        setOpen(false);
      }
    } catch {
      setNote("Could not reach the server. The free host sleeps when idle; retry in about 25 seconds.");
    } finally { setFiring(null); }
  }

  return (
    <div className="launcher">
      <button className="launcher-main" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "Close" : "Start a crisis"}
      </button>
      {open && (
        <div className="launcher-menu">
          <div className="launcher-hint">Pick what goes wrong. The right council will debate it.</div>
          {QUICK_SCENARIOS.map((s) => (
            <button key={s.key} onClick={() => fire(s.key, s.inst)} disabled={!!firing}>
              {firing === s.key ? "Starting..." : s.label}
            </button>
          ))}
        </div>
      )}
      {note && <div role="status" className="launcher-note">{note}</div>}
    </div>
  );
}

const PHASE_LABEL: Record<string, string> = {
  night: "Night",
  morning: "Morning",
  work: "Working hours",
  evening: "Evening",
};

function SpeedControl() {
  const health = useWorld((s) => s.health);
  const [local, setLocal] = useState(1.0);
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    if (health?.tick_interval != null) setLocal(health.tick_interval);
  }, [health?.tick_interval]);

  async function changeSpeed(v: number) {
    const prev = local;
    setLocal(v);
    try {
      const res = await fetch(`${API_ROOT}/speed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seconds_per_tick: v }),
      });
      if (res.status === 401 || res.status === 403) {
        // the public demo shares one simulation among all viewers, so speed is admin-only there
        setLocked(true);
        setLocal(prev);
      }
    } catch { /* ignore */ }
  }

  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 6, opacity: locked ? 0.55 : 1 }}
      title={locked ? "Speed is locked on the shared public demo (one simulation, many viewers). Run it locally to change it." : "Simulation speed: seconds of real time per tick. Lower is faster."}
    >
      <span style={{ fontSize: 11, color: "#64748b" }}>{locked ? "speed (locked)" : "speed"}</span>
      <input
        type="range" min={0.1} max={3} step={0.1}
        value={local}
        disabled={locked}
        onChange={(e) => changeSpeed(parseFloat(e.target.value))}
        style={{ width: 70, accentColor: "#6ea8fe", cursor: locked ? "not-allowed" : "pointer" }}
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
  if (pressure <= 0.05) return null;
  const pct = Math.round(pressure * 100);
  const color = pressure >= 0.75 ? "#f87171" : pressure >= 0.40 ? "#fb923c" : "#fbbf24";
  return (
    <span
      className="pill"
      title="How close the city's fear is to setting off a crisis on its own."
      style={{ color, borderColor: color, cursor: "default" }}
    >
      {pressure >= 0.99 ? "Erupting" : `Tension ${pct}%`}
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
    score >= 80 ? ["Thriving", "#4ade80"]
    : score >= 60 ? ["Stable", "#a3e635"]
    : score >= 40 ? ["Tense", "#fbbf24"]
    : score >= 20 ? ["Unstable", "#fb923c"]
    : ["Critical", "#f87171"];

  return (
    <span
      className="pill"
      title={`City stability ${score}/100 - avg fear ${Math.round(avgFear * 100)}%, ${activeCrises.length} active crisis`}
      style={{ color, borderColor: color, cursor: "default", fontWeight: 700 }}
    >
      {label} {score}
    </span>
  );
}

function SpendCounter() {
  const health = useWorld((s) => s.health);
  if (!health) return <span className="pill">AI models loading...</span>;

  const spent = health.tier2_spent_usd;
  const budget = health.tier2_budget_usd;
  const pct = Math.min(100, (spent / budget) * 100);
  const color = pct > 80 ? "#f87171" : pct > 50 ? "#fbbf24" : "#4ade80";

  return (
    <>
      {health.council_model && (
        <span className="pill" title={`Fine-tuned council model active: ${health.council_model}`} style={{ color: "#a78bfa", borderColor: "#a78bfa", cursor: "default" }}>
          model {health.council_model}
        </span>
      )}
      <span className="pill" title={`$${spent.toFixed(4)} of $${budget} AI budget used (${pct.toFixed(1)}%)`} style={{ color, borderColor: color, cursor: "default" }}>
        {health.premium_mode ? "premium" : "free"} AI · ${spent.toFixed(3)}
      </span>
    </>
  );
}

export default function App() {
  const conn = useWorld((s) => s.conn);
  const world = useWorld((s) => s.world);
  const selectedAt = useWorld((s) => s.selectedAt);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => connectWorldSocket(), []);
  // Clicking a person opens the drawer on their mind.
  useEffect(() => { if (useWorld.getState().selectedId) setDrawerOpen(true); }, [selectedAt]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>CivilizationOS</h1>
          <span className="tagline">A small city where AI people live, and AI councils govern.</span>
        </div>
        <span className="grow" />
        <span className={`live-dot ${conn === "open" ? "on" : ""}`} title={conn === "open" ? "Connected to the live simulation" : "Connecting"}>
          {conn === "open" ? "Live" : "Connecting"}
        </span>
        {world && (
          <span className="clock" title="Simulated time. One tick is about 6 in-world minutes.">
            {world.clock.replace(/^Day (\d+) /, "Day $1, ")} · {PHASE_LABEL[world.phase] ?? world.phase}
          </span>
        )}
        <button className="details-toggle" onClick={() => setDrawerOpen((o) => !o)} aria-expanded={drawerOpen}>
          {drawerOpen ? "Hide details" : "Details"}
        </button>
      </header>

      <main className={`layout ${drawerOpen ? "with-drawer" : ""}`}>
        <div className="city">
          <CityStage />
          <ScenarioLauncher />
          <Narrator />
        </div>
        {drawerOpen && (
          <aside className="sidebar" aria-label="Details">
            <div className="panel status-row">
              <StabilityBadge />
              <TensionMeter />
              <StabilitySparkline />
              <SpeedControl />
              <SpendCounter />
            </div>
            <Inspector />
            <CouncilChamber />
            <EventFeed />
            <RelationshipGraph />
            <Timeline />
            <Chronicle />
            <StatsPanel />
          </aside>
        )}
      </main>
    </div>
  );
}
