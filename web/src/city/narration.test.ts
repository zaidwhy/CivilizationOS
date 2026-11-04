import { describe, expect, it } from "vitest";
import type { WorldMessage } from "../ws/store";
import { enqueueLine, fearLine, lineForEvent, takeNext, tourLines, trimText } from "./narration";
import type { Line } from "./narration";

const ELLIPSIS = String.fromCodePoint(0x2026);
// The council code prefixes some speaker names with a scales icon; built from its code
// point so the test source stays plain text.
const SCALES_ICON = String.fromCodePoint(0x2696, 0xfe0f);

const world = {
  type: "world", tick: 120, clock: "Day 1 12:00", phase: "work", day_progress: 0.5,
  grid: { w: 24, h: 16 },
  locations: [
    { id: "clinic", name: "Mercy Clinic", type: "workplace", x: 20, y: 5 },
    { id: "market", name: "Central Market", type: "commons", x: 12, y: 8 },
    { id: "inst_health", name: "Healthcare", type: "institution", x: 20, y: 1 },
    { id: "inst_gov", name: "Government", type: "institution", x: 4, y: 1 },
  ],
  citizens: Array.from({ length: 10 }, (_, i) => ({ id: `c${i}` })),
  events: [], active_crises: [], closed_locations: [], fear_pressure: 0, factions: [],
} as unknown as WorldMessage;

const line = (text: string, weight: number, topic?: string): Line => ({ text, detail: "", focus: null, weight, topic });

describe("trimText", () => {
  it("keeps a visible ellipsis when the server cut the sentence, without a half word", () => {
    expect(trimText(`The council will immediately activate the Tiered Business R${ELLIPSIS}`)).toBe(
      "The council will immediately activate the Tiered Business...",
    );
  });

  it("leaves a complete sentence alone", () => {
    expect(trimText("Clinic partially reopened")).toBe("Clinic partially reopened");
  });
});

describe("lineForEvent", () => {
  it("names the building a crisis closed and points the camera at it", () => {
    const told = lineForEvent("crisis", "CRISIS [inst_health]: A dangerous fever is spreading.", world, ["clinic"]);
    expect(told?.text).toBe("A crisis hits the city: Mercy Clinic has closed.");
    expect(told?.detail).toBe("A dangerous fever is spreading.");
    expect(told?.focus).toEqual({ kind: "location", id: "clinic" });
    expect(told?.weight).toBe(3);
  });

  it("falls back to the council's hall when a crisis closed nothing", () => {
    const told = lineForEvent("crisis", "CRISIS [inst_gov]: Power grid failing.", world, []);
    expect(told?.text).toBe("A crisis hits the city.");
    expect(told?.focus).toEqual({ kind: "location", id: "inst_gov" });
  });

  it("drops both VERDICT prefixes from a council's plan", () => {
    const told = lineForEvent("decision", "VERDICT [inst_health]: VERDICT: Deploy mobile clinics tonight.", world, []);
    expect(told?.text).toBe("The Healthcare council has voted on a plan.");
    expect(told?.detail).toBe("Deploy mobile clinics tonight.");
  });

  it("says plainly that no AI answered, even when the server cut the marker short", () => {
    const told = lineForEvent("decision", `VERDICT [inst_gov]: [Synthesizer unavailable]${ELLIPSIS}`, world, []);
    expect(told?.detail).toBe("The AI advisers could not be reached this time, so no plan was written.");
  });

  it("strips an icon from the speaker's name and groups debate turns per council", () => {
    const told = lineForEvent("debate", `[${SCALES_ICON} Synthesizer] We reopen the clinic on generators${ELLIPSIS}`, world, [], "inst_health");
    expect(told?.text).toBe("The Healthcare council is debating what to do.");
    expect(told?.detail).toBe('Synthesizer: "We reopen the clinic on..."');
    expect(told?.topic).toBe("debate:inst_health");
  });

  it("turns a conversation into a low-priority line about the place", () => {
    const told = lineForEvent("conversation", "Greta Lind and Cleo Tanaka talk at Central Market", world, []);
    expect(told?.text).toBe("Greta and Cleo are talking at Central Market.");
    expect(told?.focus).toEqual({ kind: "location", id: "market" });
    expect(told?.weight).toBe(0);
  });

  it("ignores events it has no sentence for", () => {
    expect(lineForEvent("observation", "Ava notices the rain", world, [])).toBeNull();
  });
});

describe("fearLine", () => {
  const people = ["Ava", "Hugo", "Iris", "Ben"].map((first, i) => ({ id: `c${i}`, first, job: "Doctor. " }));

  it("names one, two, or the first two of many afraid people in one sentence", () => {
    expect(fearLine(people.slice(0, 1)).text).toBe("Ava is afraid.");
    expect(fearLine(people.slice(0, 2)).text).toBe("Ava and Hugo are afraid.");
    expect(fearLine(people.slice(0, 3)).text).toBe("Ava, Hugo and 1 other are afraid.");
    expect(fearLine(people).text).toBe("Ava, Hugo and 2 others are afraid.");
  });

  it("follows the first person named", () => {
    expect(fearLine(people).focus).toEqual({ kind: "citizen", id: "c0" });
  });
});

describe("the waiting queue", () => {
  it("replaces a queued line on the same topic instead of stacking it", () => {
    let queue = enqueueLine([], line("Healthcare debating, turn 1", 2, "debate:inst_health"));
    queue = enqueueLine(queue, line("Ava is afraid.", 2, "fear"));
    queue = enqueueLine(queue, line("Healthcare debating, turn 2", 2, "debate:inst_health"));
    expect(queue.map((l) => l.text)).toEqual(["Healthcare debating, turn 2", "Ava is afraid."]);
  });

  it("drops the least important line over the cap and keeps the crisis", () => {
    let queue = enqueueLine([], line("A crisis hits the city.", 3));
    for (let i = 0; i < 5; i++) queue = enqueueLine(queue, line(`Some people are banding together ${i}.`, 1), 4);
    expect(queue).toHaveLength(4);
    expect(queue[0].text).toBe("A crisis hits the city.");
    expect(queue.map((l) => l.text)).not.toContain("Some people are banding together 0.");
  });

  it("shows the most important line first, oldest first among equals", () => {
    const queue = [line("fear", 2), line("verdict A", 3), line("verdict B", 3)];
    const first = takeNext(queue);
    expect(first.line?.text).toBe("verdict A");
    expect(takeNext(first.rest).line?.text).toBe("verdict B");
    expect(takeNext([]).line).toBeUndefined();
  });
});

describe("tourLines", () => {
  it("introduces the city with its real population and points at the councils", () => {
    const tour = tourLines(world);
    expect(tour).toHaveLength(4);
    expect(tour[0].text).toContain("10 people live here");
    expect(tour[1].focus).toEqual({ kind: "location", id: "inst_police" });
  });
});
