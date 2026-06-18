import { create } from "zustand";

export type Citizen = {
  id: string;
  name: string;
  occupation: string;
  x: number;
  y: number;
  action: string;
  location_id: string;
  speech: string | null;
};

export type LocationT = {
  id: string;
  name: string;
  type: "home" | "workplace" | "commons" | "institution";
  x: number;
  y: number;
};

export type WorldEvent = { tick: number; kind: string; text: string };

export type WorldMessage = {
  type: "world";
  tick: number;
  clock: string;
  phase: string;
  day_progress: number;
  grid: { w: number; h: number };
  locations: LocationT[];
  citizens: Citizen[];
  events: WorldEvent[];
};

export type AgentDetail = {
  id: string;
  name: string;
  occupation: string;
  traits: string;
  action: string;
  memories: { tick: number; kind: string; text: string; importance: number }[];
  relationships: { id: string; name: string; affinity: number }[];
};

type ConnState = "connecting" | "open" | "closed";

interface WorldStore {
  conn: ConnState;
  world: WorldMessage | null;
  selectedId: string | null;
  detail: AgentDetail | null;
  setConn: (c: ConnState) => void;
  apply: (msg: WorldMessage) => void;
  select: (id: string | null) => void;
  refreshDetail: () => void;
}

export const useWorld = create<WorldStore>((set, get) => ({
  conn: "connecting",
  world: null,
  selectedId: null,
  detail: null,
  setConn: (conn) => set({ conn }),
  apply: (msg) => set({ world: msg }),
  select: (id) => {
    set({ selectedId: id, detail: null });
    if (id) get().refreshDetail();
  },
  refreshDetail: async () => {
    const id = get().selectedId;
    if (!id) return;
    try {
      const res = await fetch(`/api/agent/${id}`);
      const d = await res.json();
      if (!d.error && get().selectedId === id) set({ detail: d });
    } catch {
      /* transient; will retry on next selection */
    }
  },
}));

// Dev convenience: expose the store on window so it can be driven from the
// console (and automated checks). Tree-shaken out of production builds.
if (import.meta.env.DEV && typeof window !== "undefined") {
  (window as unknown as { useWorld: typeof useWorld }).useWorld = useWorld;
}

/** Opens the world WebSocket, wires snapshots into the store, auto-reconnects. */
export function connectWorldSocket() {
  const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
  let ws: WebSocket;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let keepalive: ReturnType<typeof setInterval> | undefined;
  let detailPoll: ReturnType<typeof setInterval> | undefined;

  const open = () => {
    useWorld.getState().setConn("connecting");
    ws = new WebSocket(url);
    ws.onopen = () => {
      useWorld.getState().setConn("open");
      keepalive = setInterval(() => ws.readyState === ws.OPEN && ws.send("ping"), 5000);
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "world") useWorld.getState().apply(msg);
    };
    ws.onclose = () => {
      useWorld.getState().setConn("closed");
      if (keepalive) clearInterval(keepalive);
      retry = setTimeout(open, 1000);
    };
    ws.onerror = () => ws.close();
  };

  open();
  // keep the open inspector panel fresh as the selected agent accrues memories
  detailPoll = setInterval(() => useWorld.getState().refreshDetail(), 4000);

  return () => {
    if (retry) clearTimeout(retry);
    if (keepalive) clearInterval(keepalive);
    if (detailPoll) clearInterval(detailPoll);
    ws?.close();
  };
}
