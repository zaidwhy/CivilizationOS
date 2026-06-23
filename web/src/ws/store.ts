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
  fear: number;
  active_crisis: string | null;
};

export type LocationT = {
  id: string;
  name: string;
  type: "home" | "workplace" | "commons" | "institution";
  x: number;
  y: number;
};

export type WorldEvent = { tick: number; kind: string; text: string };

export type Faction = {
  id: string;
  name: string;
  member_ids: string[];
  member_names: string[];
  avg_affinity: number;
  avg_fear: number;
};

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
  active_crises: string[];
  closed_locations: string[];
  fear_pressure: number;
};

export type AgentDetail = {
  id: string;
  name: string;
  occupation: string;
  traits: string;
  backstory: string;
  action: string;
  fear: number;
  active_crisis: string | null;
  memories: { tick: number; kind: string; text: string; importance: number }[];
  relationships: { id: string; name: string; affinity: number }[];
};

export type DebateTurn = {
  debate_id: string;
  institution_id: string;
  role: string;
  name: string;
  text: string;
  tick: number;
  is_final: boolean;
};

export type HealthData = {
  tick_interval: number;
  tier2_spent_usd: number;
  tier2_budget_usd: number;
  premium_mode: boolean;
  causal_events: number;
  active_crises: string[];
  council_model: string | null;
};

type ConnState = "connecting" | "open" | "closed";

interface WorldStore {
  conn: ConnState;
  world: WorldMessage | null;
  selectedId: string | null;
  detail: AgentDetail | null;
  debates: Record<string, DebateTurn[]>;
  activeDebateId: string | null;
  health: HealthData | null;
  setConn: (c: ConnState) => void;
  apply: (msg: WorldMessage) => void;
  select: (id: string | null) => void;
  refreshDetail: () => void;
  addDebateTurn: (turn: DebateTurn) => void;
  setActiveDebate: (id: string | null) => void;
  setHealth: (h: HealthData) => void;
}

const emptyDebates: Record<string, DebateTurn[]> = {};

export const useWorld = create<WorldStore>((set, get) => ({
  conn: "connecting",
  world: null,
  selectedId: null,
  detail: null,
  debates: emptyDebates,
  activeDebateId: null,
  health: null,
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
      /* transient */
    }
  },
  addDebateTurn: (turn) =>
    set((s) => {
      const prev = s.debates[turn.debate_id] ?? [];
      return {
        debates: { ...s.debates, [turn.debate_id]: [...prev, turn] },
        activeDebateId: turn.debate_id,
      };
    }),
  setActiveDebate: (id) => set({ activeDebateId: id }),
  setHealth: (h) => set({ health: h }),
}));

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
  let healthPoll: ReturnType<typeof setInterval> | undefined;

  const pollHealth = async () => {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const d = await res.json();
        useWorld.getState().setHealth({
          tick_interval: d.tick_interval ?? 1,
          tier2_spent_usd: d.tier2_spent_usd ?? 0,
          tier2_budget_usd: d.tier2_budget_usd ?? 15,
          premium_mode: d.premium_mode ?? false,
          causal_events: d.causal_events ?? 0,
          active_crises: d.active_crises ?? [],
          council_model: d.brains?.council ?? null,
        });
      }
    } catch { /* transient */ }
  };

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
      else if (msg.type === "debate_turn") useWorld.getState().addDebateTurn(msg as DebateTurn);
    };
    ws.onclose = () => {
      useWorld.getState().setConn("closed");
      if (keepalive) clearInterval(keepalive);
      retry = setTimeout(open, 1000);
    };
    ws.onerror = () => ws.close();
  };

  open();
  detailPoll = setInterval(() => useWorld.getState().refreshDetail(), 4000);
  healthPoll = setInterval(pollHealth, 5000);
  pollHealth();

  return () => {
    if (retry) clearTimeout(retry);
    if (keepalive) clearInterval(keepalive);
    if (detailPoll) clearInterval(detailPoll);
    if (healthPoll) clearInterval(healthPoll);
    ws?.close();
  };
}
