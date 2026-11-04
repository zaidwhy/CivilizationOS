import { useEffect, useRef, useState } from "react";
import { useWorld } from "../ws/store";
import type { Focus, WorldMessage } from "../ws/store";

// One plain sentence at a time about what the city is doing. Live events outrank the
// guided tour; the camera follows whatever the current sentence names.

// `topic` marks lines that replace each other while queued: the newest debate turn per
// council, and one running "who is afraid" line instead of one line per person.
type Line = { text: string; detail: string; focus: Focus; weight: number; topic?: string };
type AfraidPerson = { id: string; first: string; job: string };

const MIN_SHOW_MS = 6500;   // every sentence stays long enough to read
const IDLE_TOUR_MS = 9000;  // with nothing live to say, the tour continues after this
const BROWSE_HOLD_MS = 20000;
const AFRAID = 0.6;
const QUEUE_CAP = 12;
// The council code writes "[Role unavailable]" when no language model answered.
const NO_MODEL = /^\[[^\]]*unavailable\]/i;

// The server cuts long event text at a fixed length and ends it with an ellipsis; keep that
// visible as "..." so a cut sentence never reads as a finished one.
function trimText(text: string, max = 130) {
  const clean = text.replace(/\s+/g, " ").trim();
  const wasCut = /(…|\.\.\.)$/u.test(clean);
  const body = clean.replace(/(…|\.\.\.)+$/u, "").trim();
  if (body.length > max) return body.slice(0, max).replace(/\s+\S*$/, "") + "...";
  return wasCut ? body.replace(/\s+\S*$/, "") + "..." : body;
}

function councilName(world: WorldMessage, institutionId: string) {
  return world.locations.find((l) => l.id === institutionId)?.name ?? "city";
}

function tourLines(world: WorldMessage): Line[] {
  return [
    { text: `This is a small city. ${world.citizens.length} people live here, each one run by an AI.`,
      detail: "They go to work, meet friends, and remember what happens to them.", focus: null, weight: 0 },
    { text: "Five AI councils govern it: Government, Media, Police, Economy and Healthcare.",
      detail: "Each council is five AI advisers who debate and vote.", focus: { kind: "location", id: "inst_police" }, weight: 0 },
    { text: "Click any person to read their mind.",
      detail: "You will see their memories, who they trust, and how afraid they are.", focus: null, weight: 0 },
    { text: "Start a crisis with the button at the top right, and watch the city react.",
      detail: "Fear spreads between people, and the council in charge debates what to do.", focus: null, weight: 0 },
  ];
}

/** Turns one world event into a sentence, or null when it is not worth narrating. */
function lineForEvent(kind: string, text: string, world: WorldMessage, newlyClosed: string[]): Line | null {
  const inst = text.match(/\[(inst_[a-z]+)\]/)?.[1];
  if (kind === "crisis") {
    const what = trimText(text.replace(/^CRISIS \[[^\]]+\]:\s*/, ""));
    const closedId = newlyClosed[0];
    const closedName = closedId ? world.locations.find((l) => l.id === closedId)?.name : undefined;
    return {
      text: closedName ? `A crisis hits the city: ${closedName} has closed.` : "A crisis hits the city.",
      detail: what, focus: closedId ? { kind: "location", id: closedId } : inst ? { kind: "location", id: inst } : null, weight: 3,
    };
  }
  if (kind === "emergent") {
    const name = text.replace(/^[^A-Za-z]+/, "").split(" erupts")[0];
    return { text: `Fear boiled over into a new crisis: ${name}.`,
      detail: "Nobody started this one. People's fear grew until it broke out on its own.", focus: null, weight: 3 };
  }
  if (kind === "debate") {
    const debate = useWorld.getState();
    const turns = debate.activeDebateId ? debate.debates[debate.activeDebateId] : undefined;
    const institution = turns?.[turns.length - 1]?.institution_id;
    const speaker = (text.match(/^\[([^\]]+)\]/)?.[1] ?? "").replace(/^[^\p{L}]+/u, "") || "An adviser";
    const said = text.replace(/^\[[^\]]+\]\s*/, "");
    return {
      text: `The ${institution ? councilName(world, institution) : "city"} council is debating what to do.`,
      detail: NO_MODEL.test(said) ? "The AI advisers could not be reached this time." : `${speaker}: "${trimText(said, 110)}"`,
      focus: institution ? { kind: "location", id: institution } : null, weight: 2,
      topic: `debate:${institution ?? "unknown"}`,
    };
  }
  if (kind === "decision" && inst) {
    const raw = text.replace(/^VERDICT \[[^\]]+\]:\s*/, "").replace(/^VERDICT:\s*/i, "");
    // Checked on the raw text: trimming can cut the word "unavailable" off the end.
    const noModel = NO_MODEL.test(raw);
    const plan = trimText(raw);
    return { text: `The ${councilName(world, inst)} council has voted on a plan.`,
      detail: noModel ? "The AI advisers could not be reached this time, so no plan was written." : plan,
      focus: { kind: "location", id: inst }, weight: 3 };
  }
  if (kind === "decision") {
    return { text: "The council's plan is now in effect.", detail: trimText(text.replace(/^Council verdict applied - /, "")), focus: null, weight: 2 };
  }
  if (kind === "event" && text.startsWith("RESOLVED")) {
    return { text: "The crisis is over. The city starts to calm down.", detail: trimText(text.replace(/^RESOLVED[^:]*:\s*/, "")), focus: null, weight: 3 };
  }
  if (kind === "event" && text.startsWith("Bloc formed")) {
    return { text: "Some people are banding together.", detail: trimText(text.replace(/^Bloc formed:\s*/, "")), focus: null, weight: 1 };
  }
  if (kind === "conversation") {
    const talk = text.match(/^(.+?) and (.+?) talk at (.+)$/);
    if (!talk) return null;
    const place = world.locations.find((l) => l.name === talk[3]);
    return { text: `${talk[1].split(" ")[0]} and ${talk[2].split(" ")[0]} are talking at ${talk[3]}.`,
      detail: "Every conversation becomes a memory for both of them.", focus: place ? { kind: "location", id: place.id } : null, weight: 0 };
  }
  return null;
}

function fearLine(people: AfraidPerson[]): Line {
  const names = people.map((p) => p.first);
  const text = names.length === 1 ? `${names[0]} is afraid.`
    : names.length === 2 ? `${names[0]} and ${names[1]} are afraid.`
    : `${names[0]}, ${names[1]} and ${names.length - 2} ${names.length === 3 ? "other" : "others"} are afraid.`;
  const spread = "Fear spreads as people talk to each other.";
  return { text, detail: names.length === 1 ? `${people[0].job}${spread}` : spread,
    focus: { kind: "citizen", id: people[0].id }, weight: 2, topic: "fear" };
}

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

  function enqueue(line: Line) {
    const same = line.topic ? queue.current.findIndex((l) => l.topic === line.topic) : -1;
    if (same !== -1) queue.current[same] = line;
    else queue.current.push(line);
    // Over the cap, drop the oldest of the least important lines, so a crisis or verdict survives.
    while (queue.current.length > QUEUE_CAP) {
      const lowest = Math.min(...queue.current.map((l) => l.weight));
      queue.current.splice(queue.current.findIndex((l) => l.weight === lowest), 1);
    }
  }

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
    for (const e of firstLook ? [] : fresh) {
      const line = lineForEvent(e.kind, e.text, world, newlyClosed);
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
        const best = Math.max(...queue.current.map((l) => l.weight));
        const at = queue.current.findIndex((l) => l.weight === best);
        next = queue.current.splice(at, 1)[0];
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
