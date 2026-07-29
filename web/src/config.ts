// In dev, Vite's proxy (vite.config.ts) forwards /api and /ws to the local
// backend, so both env vars are unset and these fall back to relative/
// same-origin URLs. In production (frontend and backend on separate hosts,
// e.g. Vercel + Render) set VITE_API_BASE and VITE_WS_URL to the deployed
// backend's origin.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
