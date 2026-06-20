# CivilizationOS — Phase 6 Handoff Log

**Date:** 2026-06-20  
**Phase:** 6 — Verdict effects, real relationship graph, stats panel  
**Branch:** main  
**Version:** 0.6.0  

---

## What Was Built in Phase 6

Phase 6 addresses three of the four "Known Limitations" from the Phase 5 handoff:

1. **Council verdict → world-state effects** (closes the governance loop)  
2. **Real relationship graph** (weighted affinity edges, not co-location proximity)  
3. **Stats dashboard panel** (fear histogram, session counters, memory league table)

---

### Backend

#### `api/sim/crisis.py` — `template_key` on `Crisis`
Added `template_key: str | None = None` field to the `Crisis` dataclass. Updated `CrisisRegistry.create()` to accept and store it. This is the key that connects a live crisis back to its originating `CrisisTemplate` so verdict effects can be applied.

#### `api/sim/events.py` — `verdict_fear_reduction` on `CrisisTemplate`
Added `verdict_fear_reduction: float = 0.12` field. When the Synthesizer delivers a verdict for a template-backed crisis, each citizen's fear drops by this amount. Default 0.12 keeps verdict effects meaningful but smaller than full resolution (which drops 0.30).

#### `api/sim/engine.py` — Verdict effects + `_apply_verdict_effects()`
- `inject_crisis()` now passes `template_key` to `crises.create()`.
- `_run_debate()`: after the verdict is written to the causal graph, checks `crisis.template_key` and calls `_apply_verdict_effects(tmpl, verdict_text)` if a template exists.
- **`_apply_verdict_effects(tmpl, verdict_text)`** (new method):
  - Reduces every citizen's fear by `tmpl.verdict_fear_reduction`.
  - Adds a `"decision"` kind memory to every citizen: `"Council issued directive on <crisis name>: <first 100 chars of verdict>"`. This gives citizens historical context for future TCMF retrieval — they *remember* that the council acted.
  - Logs a `"decision"` event to the event feed.

**Why this closes the loop:** The causal graph previously recorded `crisis → debate → decision` as text only. Now the decision actually mutates world state (fear) and propagates into citizen memory. Future crises in the same domain will see verdicts as relevant ancestors in TCMF retrieval, making councils historically aware.

#### `api/main.py` — Two new endpoints

- **`GET /graph`** — Returns `{ nodes, edges }`.
  - `nodes`: `[{ id, name, occupation, fear }]` for every citizen.
  - `edges`: `[{ source, target, weight, positive }]` — deduplicated affinity pairs where `|weight| > 0.05`. Weight is the raw relationship float (−1 to 1). Only edges above the threshold are returned to keep the graph readable.
  
- **`GET /stats`** — Returns simulation metrics for the StatsPanel:
  - `fear_buckets`: 5-element array counting citizens in each 20% fear band.
  - `avg_fear`: population average.
  - `memory_counts`: `{ citizen_name: count }` — how many memories each citizen has accumulated.
  - `total_debates`, `active_crises`, `causal_events`, `tick`.

Version bumped to `0.6.0`.

---

### Frontend

#### `web/src/panels/RelationshipGraph.tsx` — Real affinity edges
Replaced the co-location edge approximation with a proper affinity graph:
- Polls `GET /api/graph` every 6 seconds.
- **Green edges** = positive affinity (trust), **red edges** = negative affinity (tension).
- Edge **thickness** scales with `|weight| × 3` — a strong relationship is visually thick.
- Edge **opacity** scales with `|weight| × 1.5` (capped at 0.9) — faint edges = weak relationships.
- While the graph is loading (first render) falls back to faint co-location lines as before.
- Legend updated: "trust · tension" instead of just "co-located".
- Canvas height increased from 180 → 200px to fit the updated legend.
- Edge count badge shows live number of active bonds (hidden when 0).

#### `web/src/panels/StatsPanel.tsx` — NEW
Polls `GET /api/stats` every 5 seconds. Three sections:

1. **Fear Histogram**: Canvas bar chart with 5 buckets (0–20%, 20–40%, 40–60%, 60–80%, 80–100%). Each bar is colour-coded green → amber → red. Bar height is proportional to citizen count; count label appears above each bar. Average fear shown as `avg X%`.

2. **Session Counters**: 3-cell grid showing `debates`, `causal nodes`, `active crises` — each with a coloured value and subtle border.

3. **Memory League Table**: Horizontal bar chart of memories per citizen, sorted descending. First-name only, purple bars, count on the right.

Tick number shown as a tiny footer for orientation. Panel returns `null` until first stats fetch so the sidebar doesn't flicker on load.

#### `web/src/App.tsx` — StatsPanel added
`<StatsPanel />` imported and placed below `<Timeline />` in the sidebar.

---

## Architecture Decisions Made

1. **Verdict effects use `template_key`, not free-text parsing** — Parsing "VERDICT: open the clinic" with regex is brittle. Instead the `CrisisTemplate` carries `verdict_fear_reduction` as a structured scalar, and `_apply_verdict_effects` reads it. This is deterministic, testable, and avoids NLP failure modes.

2. **`Crisis.template_key` is nullable** — Custom (free-text) crises have no template, so `template_key = None` and no verdict effects fire. This is correct: we don't know what the right fear reduction should be for an ad-hoc crisis. Future work could ask the user to annotate custom crises with a template.

3. **`/graph` deduplicates edges by sorted ID pair** — Each pair `(a, b)` only appears once even though both `a.relationships[b]` and `b.relationships[a]` exist independently. The edge `weight` is taken from whichever direction is encountered first (they converge as conversations happen from both sides, but may differ slightly in the short term).

4. **Affinity threshold `|weight| > 0.05` in `/graph`** — Prevents cluttering the graph with near-zero transient edges that form every time two citizens happen to stand near each other. The 0.05 threshold keeps only edges that represent a meaningful social history.

5. **`StatsPanel` returns `null` until first fetch** — Avoids layout shift. The panel is the last item in the sidebar so a brief blank before the first 5-second poll is invisible in practice.

---

## Known Limitations / Next Steps

- **Custom crisis resolution by ID**: The `✓ resolve` button in CouncilChamber still only works for template crises (matched by `template.name === crisis_name`). A `POST /crisis/id/{crisis_id}/resolve` endpoint — resolving based on `CrisisRegistry` membership — would fix this. The `crisis_id` is already returned by `POST /crisis` and `GET /crises`.

- **Verdict effects don't reopen locations**: Locations closed by a template (e.g., clinic during pandemic) only reopen on explicit `✓ resolve`. This is intentional — a council *deciding* to act is not the same as the crisis being over. But adding `verdict_reopens: list[str]` to `CrisisTemplate` and partially reopening on verdict would make the loop richer.

- **Relationship graph forces**: The current layout is a fixed circle. A force-directed layout (repulsion between nodes, attraction along edges) would make cluster structure visible — highly-connected citizens would naturally cluster together.

- **Fine-tuned model**: `ml/train_lora.ipynb` exists; the model can be exported to GGUF, loaded into Ollama, and wired via `ollama_council_model` in `.env`.

- **Deploy**: `cd web && vercel` deploys the frontend. Backend must run locally (Ollama dependency).

---

## File Change Summary

| File | Change type |
|---|---|
| `api/sim/crisis.py` | Added `template_key` field to `Crisis` dataclass and `create()` |
| `api/sim/events.py` | Added `verdict_fear_reduction` field to `CrisisTemplate` |
| `api/sim/engine.py` | Pass `template_key` in `inject_crisis()`; call `_apply_verdict_effects()` post-verdict; new method |
| `api/main.py` | New `GET /graph`, `GET /stats` endpoints; version → 0.6.0 |
| `web/src/panels/RelationshipGraph.tsx` | Real affinity edges from `/api/graph`, weighted + coloured |
| `web/src/panels/StatsPanel.tsx` | **NEW** — fear histogram, session counters, memory league table |
| `web/src/App.tsx` | Import + render `<StatsPanel />` |
