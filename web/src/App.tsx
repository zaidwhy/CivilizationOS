import { useEffect } from "react";
import { connectWorldSocket, useWorld } from "./ws/store";
import CityStage from "./city/CityStage";
import Inspector from "./panels/Inspector";
import EventFeed from "./panels/EventFeed";
import CouncilChamber from "./panels/CouncilChamber";

const PHASE_LABEL: Record<string, string> = {
  night: "🌙 Night",
  morning: "🌅 Morning",
  work: "🏙️ Work",
  evening: "🌆 Evening",
};

export default function App() {
  const conn = useWorld((s) => s.conn);
  const world = useWorld((s) => s.world);

  useEffect(() => connectWorldSocket(), []);

  return (
    <div className="app">
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
        <span className="grow" />
        <span className="pill">free brains · $0</span>
      </header>

      <main className="layout">
        <div className="city">
          <CityStage />
        </div>
        <aside className="sidebar">
          <Inspector />
          <EventFeed />
          <CouncilChamber />
        </aside>
      </main>
    </div>
  );
}
