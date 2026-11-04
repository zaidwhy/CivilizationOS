import type { Focus, WorldMessage } from "../ws/store";

// Pure narration rules: which world events become a sentence, how they are worded, and how
// the waiting queue is ordered. Narrator.tsx owns the timing and the rendering.

// `topic` marks lines that replace each other while queued: the newest debate turn per
// council, and one running "who is afraid" line instead of one line per person.
export type Line = { text: string; detail: string; focus: Focus; weight: number; topic?: string };
export type AfraidPerson = { id: string; first: string; job: string };

export const MIN_SHOW_MS = 6500;   // every sentence stays long enough to read
export const IDLE_TOUR_MS = 9000;  // with nothing live to say, the tour continues after this
export const BROWSE_HOLD_MS = 20000;
export const AFRAID = 0.6;
export const QUEUE_CAP = 12;
// The council code writes "[Role unavailable]" when no language model answered.
const NO_MODEL = /^\[[^\]]*unavailable\]/i;

// The server cuts long event text at a fixed length and ends it with an ellipsis; keep that
// visible as "..." so a cut sentence never reads as a finished one.
export function trimText(text: string, max = 130) {
  const clean = text.replace(/\s+/g, " ").trim();
  const wasCut = /(…|\.\.\.)$/u.test(clean);
  const body = clean.replace(/(…|\.\.\.)+$/u, "").trim();
  if (body.length > max) return body.slice(0, max).replace(/\s+\S*$/, "") + "...";
  return wasCut ? body.replace(/\s+\S*$/, "") + "..." : body;
}

function councilName(world: WorldMessage, institutionId: string) {
  return world.locations.find((l) => l.id === institutionId)?.name ?? "city";
}

export function tourLines(world: WorldMessage): Line[] {
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
export function lineForEvent(
  kind: string, text: string, world: WorldMessage, newlyClosed: string[], debateInstitution?: string,
): Line | null {
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
    const institution = debateInstitution;
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

export function fearLine(people: AfraidPerson[]): Line {
  const names = people.map((p) => p.first);
  const text = names.length === 1 ? `${names[0]} is afraid.`
    : names.length === 2 ? `${names[0]} and ${names[1]} are afraid.`
    : `${names[0]}, ${names[1]} and ${names.length - 2} ${names.length === 3 ? "other" : "others"} are afraid.`;
  const spread = "Fear spreads as people talk to each other.";
  return { text, detail: names.length === 1 ? `${people[0].job}${spread}` : spread,
    focus: { kind: "citizen", id: people[0].id }, weight: 2, topic: "fear" };
}

/** Adds a line to the waiting queue. A line with a topic replaces the queued line with the same
 *  topic; over the cap the oldest of the least important lines goes, so a crisis survives. */
export function enqueueLine(queue: Line[], line: Line, cap = QUEUE_CAP): Line[] {
  const next = [...queue];
  const same = line.topic ? next.findIndex((l) => l.topic === line.topic) : -1;
  if (same !== -1) next[same] = line;
  else next.push(line);
  while (next.length > cap) {
    const lowest = Math.min(...next.map((l) => l.weight));
    next.splice(next.findIndex((l) => l.weight === lowest), 1);
  }
  return next;
}

/** The next line to show: the most important waiting line, oldest first among equals. */
export function takeNext(queue: Line[]): { line: Line | undefined; rest: Line[] } {
  if (!queue.length) return { line: undefined, rest: queue };
  const best = Math.max(...queue.map((l) => l.weight));
  const at = queue.findIndex((l) => l.weight === best);
  return { line: queue[at], rest: [...queue.slice(0, at), ...queue.slice(at + 1)] };
}
