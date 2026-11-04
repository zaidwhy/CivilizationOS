import { useEffect, useRef, useState } from "react";
import { useWorld } from "../ws/store";
import {
  AFRAID, BROWSE_HOLD_MS, IDLE_TOUR_MS, MIN_SHOW_MS,
  enqueueLine, fearLine, lineForEvent, takeNext, tourLines,
} from "./narration";
import type { AfraidPerson, Line } from "./narration";

// One plain sentence at a time about what the city is doing. Live events outrank the
// guided tour; the camera follows whatever the current sentence names.

export default function Narrator() {
  const [shown, setShown] = useState<Line | null>(null);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const history = useRef<Line[]>([]);
  const queue = useRef<Line[]>([]);
  const ambient = useRef<Line | null>(null);
  const shownAt = useRef(0);
  const tourIndex = useRef(0);
  const ambientTurn = useRef(false);
  const lastTick = useRef(-1);
  const lastCrisisAt = useRef(0);
  const afraidQueued = useRef<AfraidPerson[]>([]);
  const browseUntil = useRef(0);
  const seenEvents = useRef<Set<string>>(new Set());
  const primed = useRef(false);
  const prevClosed = useRef<Set<string>>(new Set());
  const afraidNow = useRef<Set<string>>(new Set());

  const enqueue = (line: Line) => { queue.current = enqueueLine(queue.current, line); };

  // Live events and fear changes become queued sentences.
  useEffect(() => useWorld.subscribe((state, prev) => {
    const world = state.world;
    if (!world || world === prev.world) return;
    // The server restarted (its tick went back): start fresh so replayed events are not muted.
    if (world.tick < lastTick.current - 5) {
      seenEvents.current = new Set();
      primed.current = false;
      afraidNow.current = new Set();
      afraidQueued.current = [];
      queue.current = [];
    }
    lastTick.current = world.tick;
    const closedNow = new Set(world.closed_locations ?? []);
    const newlyClosed = [...closedNow].filter((id) => !prevClosed.current.has(id));
    prevClosed.current = closedNow;

    // Events are matched by identity, not by tick: a crisis or verdict is stamped with a tick
    // the client has already seen, so "newer than the last tick" would drop it.
    const keyOf = (e: { tick: number; kind: string; text: string }) => `${e.tick}|${e.kind}|${e.text}`;
    const firstLook = seenEvents.current.size === 0 && !primed.current;
    primed.current = true;
    const fresh = world.events.filter((e) => !seenEvents.current.has(keyOf(e)));
    for (const e of fresh) seenEvents.current.add(keyOf(e));
    if (seenEvents.current.size > 200) seenEvents.current = new Set(world.events.map(keyOf));
    const turns = state.activeDebateId ? state.debates[state.activeDebateId] : undefined;
    const debating = turns?.[turns.length - 1]?.institution_id;
    for (const e of firstLook ? [] : fresh) {
      const line = lineForEvent(e.kind, e.text, world, newlyClosed, debating);
      if (!line) continue;
      if (line.weight === 0) { ambient.current = line; continue; }
      // One crisis logs a "crisis" event per council it touches; tell it once.
      if (e.kind === "crisis" && (queue.current.some((l) => l.topic === "crisis") || Date.now() - lastCrisisAt.current < 20000)) continue;
      if (e.kind === "crisis") { line.topic = "crisis"; lastCrisisAt.current = Date.now(); }
      enqueue(line);
    }

    let fearChanged = false;
    for (const c of world.citizens) {
      const wasAfraid = afraidNow.current.has(c.id);
      if (c.fear >= AFRAID && !wasAfraid) {
        afraidNow.current.add(c.id);
        const job = c.occupation ? c.occupation[0].toUpperCase() + c.occupation.slice(1) + ". " : "";
        afraidQueued.current.push({ id: c.id, first: c.name.split(" ")[0], job });
        fearChanged = true;
      } else if (c.fear < AFRAID - 0.1 && wasAfraid) {
        afraidNow.current.delete(c.id);
        afraidQueued.current = afraidQueued.current.filter((p) => p.id !== c.id);
        fearChanged = true;
      }
    }
    // One running line names everyone who became afraid and has not been narrated yet.
    if (fearChanged) {
      queue.current = queue.current.filter((l) => l.topic !== "fear");
      if (afraidQueued.current.length) enqueue(fearLine(afraidQueued.current));
    }
  }), []);

  // The pacing loop: show the most important waiting sentence, or continue the tour.
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      const world = useWorld.getState().world;
      if (!world || now < browseUntil.current) return;
      const elapsed = now - shownAt.current;
      let next: Line | undefined;
      if (elapsed >= MIN_SHOW_MS && queue.current.length) {
        const taken = takeNext(queue.current);
        next = taken.line!;
        queue.current = taken.rest;
        if (next.topic === "fear") afraidQueued.current = [];
      } else if (elapsed >= IDLE_TOUR_MS || shownAt.current === 0) {
        // Tour sentences and "who is talking" lines take turns; each keeps its own place.
        if (ambientTurn.current && ambient.current) {
          next = ambient.current;
          ambient.current = null;
        } else {
          const tour = tourLines(world);
          next = tour[tourIndex.current % tour.length];
          tourIndex.current++;
        }
        ambientTurn.current = !ambientTurn.current;
      }
      if (!next) return;
      shownAt.current = now;
      history.current = [...history.current, next].slice(-30);
      setHistoryIndex(-1);
      setShown(next);
      useWorld.getState().setFocus(next.focus);
    }, 500);
    return () => clearInterval(timer);
  }, []);

  function browse(step: number) {
    const lines = history.current;
    if (!lines.length) return;
    const current = historyIndex === -1 ? lines.length - 1 : historyIndex;
    const target = Math.min(lines.length - 1, Math.max(0, current + step));
    browseUntil.current = Date.now() + BROWSE_HOLD_MS;
    setHistoryIndex(target === lines.length - 1 ? -1 : target);
    setShown(lines[target]);
    useWorld.getState().setFocus(lines[target].focus);
  }

  if (!shown) return null;
  const atNewest = historyIndex === -1;
  const atOldest = historyIndex === 0 || history.current.length <= 1;
  const person = shown.focus?.kind === "citizen" ? shown.focus.id : null;
  return (
    <div className="narrator">
      <button className="narrator-step" onClick={() => browse(-1)} disabled={atOldest} aria-label="Previous sentence">&#8249;</button>
      {/* Only live news is announced to screen readers; the looping tour stays quiet. */}
      <p key={shown.text + shown.detail} aria-live={shown.weight >= 2 ? "polite" : "off"}>
        {shown.text}
        {shown.detail && <small>{shown.detail}</small>}
      </p>
      {person && (
        <button className="narrator-act" onClick={() => useWorld.getState().select(person)}>Read their mind</button>
      )}
      <button className="narrator-step" onClick={() => browse(1)} disabled={atNewest} aria-label="Next sentence">&#8250;</button>
    </div>
  );
}
