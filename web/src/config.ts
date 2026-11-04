// The backend serves its routes at the root (/stats, /crisis). In dev, Vite's
// proxy (vite.config.ts) maps /api/* onto the local backend and strips the
// prefix, so the default root is "/api". In production (frontend and backend
// on separate hosts, e.g. Vercel + Render) VITE_API_BASE is the backend's
// origin and requests go straight to its root, with no /api prefix.
// A trailing slash in the env value would otherwise produce "//crisis".
export const API_ROOT = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/+$/, "");

export const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
