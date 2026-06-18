import { create } from "zustand";

// Phase 0 message shape (heartbeat). Phase 1 extends this into full world state.
export type ServerMessage = {
  type: "tick";
  tick: number;
  premium_mode: boolean;
};

type ConnState = "connecting" | "open" | "closed";

interface WorldStore {
  conn: ConnState;
  tick: number;
  premiumMode: boolean;
  setConn: (c: ConnState) => void;
  apply: (msg: ServerMessage) => void;
}

export const useWorld = create<WorldStore>((set) => ({
  conn: "connecting",
  tick: 0,
  premiumMode: false,
  setConn: (conn) => set({ conn }),
  apply: (msg) => {
    if (msg.type === "tick") {
      set({ tick: msg.tick, premiumMode: msg.premium_mode });
    }
  },
}));

/** Opens the world WebSocket and wires messages into the store. Auto-reconnects. */
export function connectWorldSocket() {
  const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
  let ws: WebSocket;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    useWorld.getState().setConn("connecting");
    ws = new WebSocket(url);
    ws.onopen = () => useWorld.getState().setConn("open");
    ws.onmessage = (e) => useWorld.getState().apply(JSON.parse(e.data));
    ws.onclose = () => {
      useWorld.getState().setConn("closed");
      retry = setTimeout(open, 1000);
    };
    ws.onerror = () => ws.close();
  };

  open();
  return () => {
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}
