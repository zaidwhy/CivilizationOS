# CivilizationOS — Phase 8 Handoff

**Date:** 2026-06-21 | **Version:** 0.8.0 | **Tests:** 54 passing | **TS errors:** 0

---

## What Phase 8 Addressed

Three items from the original project plan that were still open entering this session:

| # | Feature | Status in Phase 7 |
|---|---|---|
| A | Speech bubbles above citizen sprites | Code existed but visual quality was poor (no tail, name prefix not stripped, TTL too short) |
| B | Graph hover tooltip | Force-directed graph had no hover interaction beyond click-to-select |
| C | Wire fine-tuned model | `OLLAMA_COUNCIL_MODEL` config hook existed; runtime bug meant it was never actually used |

---

## A — Speech Bubbles

### Problem

The bubble rendering in `CityStage.tsx` had four visual issues:
1. Raw speech included the speaker name prefix (`"Ava Chen: Hello"`) — the citizen label below already shows the name, so this was redundant text inside the bubble.
2. 80-char cap meant bubbles could be too wide.
3. No downward pointer triangle — nothing visually connected the bubble to the speaker.
4. TTL was 4 ticks (~4 seconds) — too short to read anything meaningful.

### What changed

**`api/agents/citizen.py`** — `say()` TTL default: `4 → 10`

```python
def say(self, text: str, ttl: int = 10) -> None:
    self.speech = text
    self.speech_ttl = ttl
```

**`web/src/city/CityStage.tsx`** — `speechStyle` wordWrapWidth: `150 → 120`

```ts
const speechStyle = new TextStyle({ fill: 0x0b0e14, fontSize: 11, wordWrap: true, wordWrapWidth: 120 });
```

**`web/src/city/CityStage.tsx`** — `sync()` speech block rewritten:

```tsx
if (c.speech) {
  // Strip "Name: " prefix — name is already shown in the label below
  const raw = c.speech;
  const colonIdx = raw.indexOf(": ");
  const dialogue = colonIdx !== -1 ? raw.slice(colonIdx + 2) : raw;
  const display = dialogue.length > 50 ? dialogue.slice(0, 49) + "…" : dialogue;
  s.bubbleText.text = display;

  const bg = (s.bubble as unknown as { _bg: Graphics })._bg;
  bg.clear();
  const bw = s.bubbleText.width + 16;
  const bh = s.bubbleText.height + 10;
  // Bubble body
  bg.roundRect(0, 0, bw, bh, 6).fill({ color: 0xf2f6ff });
  // Downward pointer triangle centred at bottom
  const px = bw / 2;
  bg.poly([px - 5, bh, px + 5, bh, px, bh + 7]).fill({ color: 0xf2f6ff });

  s.bubble.x = -(bw / 2);
  s.bubble.y = -(bh + 7 + 18); // 18px gap above the dot top
  s.bubble.visible = true;
} else {
  s.bubble.visible = false;
}
```

### How it works now

- `"Ava Chen: The market feels tense today"` renders as `"The market feels tense today"`
- Capped at 50 characters with `…` ellipsis
- Rounded white-blue bubble with a small downward-pointing triangle centred at the bottom, tip touching 18 px above the citizen's dot
- Bubble width adjusts to text dynamically (`bubbleText.width + 16`)
- Visible for ~10 seconds at 1 tick/s

---

## B — Graph Hover Tooltip

### Problem

The force-directed graph only supported click (select citizen). Hovering over a node gave no feedback about who it was or their relationships.

### What changed

**`web/src/panels/RelationshipGraph.tsx`** — full rewrite adding tooltip state and event handlers.

#### New types

```ts
type TooltipData = {
  name: string;
  occupation: string;
  fear: number;
  bonds: { name: string; weight: number; positive: boolean }[];
  x: number;
  y: number;
};
```

#### State

```ts
const [tooltip, setTooltip] = useState<TooltipData | null>(null);
```

#### Mouse handler

```ts
function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
  const rect = canvasRef.current!.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const cs = citizensRef.current;
  const g = graphRef.current;
  if (!cs) { setTooltip(null); return; }

  let hoveredId: string | null = null;
  for (const c of cs) {
    const p = physRef.current.get(c.id);
    if (p && Math.hypot(mx - p.x, my - p.y) <= R + 6) {
      hoveredId = c.id;
      break;
    }
  }
  if (!hoveredId) { setTooltip(null); return; }

  const citizen = cs.find((c) => c.id === hoveredId);
  const bonds = [];
  if (g?.edges) {
    for (const edge of g.edges) {
      const otherId = edge.source === hoveredId ? edge.target
        : edge.target === hoveredId ? edge.source : null;
      if (!otherId) continue;
      const other = cs.find((c) => c.id === otherId);
      if (other) bonds.push({ name: other.name.split(" ")[0], weight: Math.abs(edge.weight), positive: edge.positive });
    }
    bonds.sort((a, b) => b.weight - a.weight);
  }
  const p = physRef.current.get(hoveredId)!;
  setTooltip({ name: citizen.name, occupation: citizen.occupation, fear: citizen.fear, bonds: bonds.slice(0, 3), x: p.x, y: p.y });
}
```

#### Tooltip rendering

The canvas is wrapped in a `<div style={{ position: "relative" }}>`. An HTML overlay div is positioned absolutely using the physics node's canvas-space coordinates, with automatic left-flip when the node is in the right half of the canvas:

```tsx
const tipLeft = tooltip.x > W / 2 ? tooltip.x - 148 : tooltip.x + 14;
const tipTop  = Math.max(0, tooltip.y - 14);
```

Tooltip shows: full name (bold), occupation (muted), fear % (coloured by fearColor()), top 3 bonds with ♥/⚡ icon and affinity %.

`onMouseLeave` on the canvas clears the tooltip.

---

## C — Fine-Tuned Council Model Wired

### The Bug

`council.py` was passing `local_model` to `router.complete()` but only when `spec["tier"] == Tier.LOCAL`. All 5 ROLE_SPECS are defined with `Tier.FREE` or `Tier.PREMIUM` — never `Tier.LOCAL`. So `local_model` was always `None` regardless of env var.

```python
# BROKEN (before Phase 8):
local_override = s.ollama_council_model if s.has_finetuned_council else None
result = await router.complete(
    ...
    tier=spec["tier"],
    local_model=local_override if spec["tier"] == Tier.LOCAL else None,  # always None
)
```

### The Fix

**`api/agents/council.py`** — `Council.deliberate()`:

```python
is_synth = spec["role"] == "Synthesizer"
if s.has_finetuned_council and not is_synth:
    # Route all debate roles through the fine-tuned local model;
    # Synthesizer keeps its Tier.PREMIUM path (Claude verdict).
    effective_tier = Tier.LOCAL
    local_model = s.ollama_council_model
else:
    effective_tier = spec["tier"]
    local_model = None
result = await router.complete(
    prompt=user_prompt,
    system=spec["system"],
    tier=effective_tier,
    max_tokens=200,
    temperature=0.72,
    local_model=local_model,
)
```

**Design decision:** Synthesizer is deliberately excluded from the fine-tuned path. The Synthesizer issues the binding VERDICT and benefits most from Claude's reasoning. The four debate roles (Historian, Strategist, Skeptic, Predictor) are where the custom persona voice matters — these use the fine-tuned model when available.

### /health exposure

**`api/main.py`** — `/health` response now includes:
```json
"brains": {
  "local": "qwen2.5:3b",
  "council": "civos-council",   // null if OLLAMA_COUNCIL_MODEL not set
  "free": "gemini-2.0-flash",
  "premium": "claude-haiku-20240307"
}
```

### Frontend indicator

**`web/src/ws/store.ts`** — `HealthData` type:
```ts
council_model: string | null;
```

Poll extracts it as: `council_model: d.brains?.council ?? null`

**`web/src/App.tsx`** — `SpendCounter` now renders a purple pill when active:
```tsx
{health.council_model && (
  <span className="pill" title={`Fine-tuned council model active: ${health.council_model}`}
    style={{ color: "#a78bfa", borderColor: "#a78bfa", cursor: "default" }}>
    🧠 {health.council_model}
  </span>
)}
```

### How to activate

```bash
# In .env
OLLAMA_COUNCIL_MODEL=civos-council

# Before that, export from the Colab notebook:
# File → Download → .gguf, then:
ollama create civos-council -f Modelfile
```

Once set, `has_finetuned_council` returns `True` and all 4 debate roles route to Ollama with the named model. The purple pill appears in the header confirming activation.

---

## Files Changed in Phase 8

| File | Change |
|---|---|
| `api/agents/citizen.py` | `say()` TTL default `4 → 10` |
| `api/agents/council.py` | Fixed fine-tuned model routing logic — `effective_tier` + `local_model` |
| `api/main.py` | `/health` now exposes `brains.council` |
| `web/src/city/CityStage.tsx` | Bubble: name strip, 50-char cap, pointer tail, dynamic repositioning, narrower wordWrap |
| `web/src/panels/RelationshipGraph.tsx` | Hover tooltip: `TooltipData` type, `handleMouseMove`, HTML overlay render, left-flip logic |
| `web/src/ws/store.ts` | `HealthData.council_model: string | null`, health poll extracts `d.brains?.council` |
| `web/src/App.tsx` | `SpendCounter` renders purple `🧠 model-name` pill when fine-tuned council active |

---

## Test Status

54 tests, all passing. No new tests added in Phase 8 (all changes are rendering-only or a one-method bug fix with no state machine impact).

---

## What Remains

| Item | Notes |
|---|---|
| Vercel deploy | Frontend ready; backend has Ollama dependency (needs ngrok or self-host for public URL) |
| "Rewind story" scrubber | Not in any handoff; causal graph exists but no timeline scrubbing UI |
| Demo video | No recording tooling in repo |
| Sixth crisis template | Easy win — Housing Crisis (inst_economy) is a good candidate |
| Fine-tuned GGUF export | Notebook exists (`ml/train_lora.ipynb`); run on Colab T4, export, then `ollama create` |
| CouncilChamber: collapse old debates | UX debt — many debates pile up with no archiving/collapse |
