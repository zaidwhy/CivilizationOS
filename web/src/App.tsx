import { useEffect } from "react";
import { connectWorldSocket, useWorld } from "./ws/store";

export default function App() {
  const conn = useWorld((s) => s.conn);
  const tick = useWorld((s) => s.tick);
  const premiumMode = useWorld((s) => s.premiumMode);

  useEffect(() => connectWorldSocket(), []);

  return (
    <div className="app">
      <header className="topbar">
        <h1>CIVILIZATION&nbsp;OS</h1>
        <span className={`pill ${conn === "open" ? "live" : "off"}`}>
          {conn === "open" ? "● live" : conn}
        </span>
        <span className="pill">{premiumMode ? "premium brains" : "free brains ($0)"}</span>
      </header>

      <main className="stage">
        <div style={{ textAlign: "center" }}>
          <div className="tick">{tick}</div>
          <div>world clock ticks (Phase 0 heartbeat)</div>
        </div>
      </main>
    </div>
  );
}
