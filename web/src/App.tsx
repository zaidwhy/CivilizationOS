import { useEffect, useState } from "react";
import { connectWorldSocket, useWorld } from "./ws/store";
import CityStage from "./city/CityStage";
import Inspector from "./panels/Inspector";
import EventFeed from "./panels/EventFeed";
import CouncilChamber from "./panels/CouncilChamber";
import RelationshipGraph from "./panels/RelationshipGraph";
import Timeline from "./panels/Timeline";
import StatsPanel from "./panels/StatsPanel";
import Onboarding from "./components/Onboarding";

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

function SpendCounter() {
  const health = useWorld((s) => s.health);
  if (!health) return <span className="pill">brains · loading…</span>;

  const spent = health.tier2_spent_usd;
  const budget = health.tier2_budget_usd;
  const pct = Math.min(100, (spent / budget) * 100);
  const color = pct > 80 ? "#f87171" : pct > 50 ? "#fbbf24" : "#4ade80";

  return (
    <span
      className="pill"
      title={`$${spent.toFixed(4)} of $${budget} Claude budget used (${pct.toFixed(1)}%)`}
      style={{ color, borderColor: color, cursor: "default" }}
    >
      {health.premium_mode ? "⚡ premium" : "⚙ free"} · ${spent.toFixed(3)}
    </span>
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
        <span className="grow" />
        <SpeedControl />
        <SpendCounter />
      </header>

      <main className="layout">
        <div className="city">
          <CityStage />
        </div>
        <aside className="sidebar">
          <Inspector />
          <RelationshipGraph />
          <EventFeed />
          <CouncilChamber />
          <Timeline />
        </aside>
      </main>
    </div>
  );
}
