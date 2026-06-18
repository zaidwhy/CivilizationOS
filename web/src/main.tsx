import { createRoot } from "react-dom/client";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import "./index.css";

// No StrictMode: it double-invokes effects in dev, racing the imperative Pixi
// canvas lifecycle in CityStage. Production never double-invokes.
createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
