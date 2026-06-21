# CivilizationOS — Phase 7 Handoff Log

**Date:** 2026-06-21  
**Phase:** 7 — Crisis-by-ID resolution, verdict location reopening, force-directed graph  
**Branch:** main  
**Version:** 0.7.0  

---

## What Was Built in Phase 7

Phase 7 closes all four Known Limitations from the Phase 6 handoff:

1. **`POST /crisis/id/{crisis_id}/resolve`** — resolve any crisis (template or custom) by registry ID
2. **`verdict_reopens`** on `CrisisTemplate` — locations partially reopen when council delivers verdict
3. **Force-directed relationship graph** — physics-based layout replaces fixed circle
4. **Custom crisis UI** — unresolved free-text crises shown in CouncilChamber with resolve buttons

---

### Backend

#### `api/sim/events.py` — `verdict_reopens` on `CrisisTemplate`
Added `verdict_reopens: list[str] = field(default_factory=list)` to `CrisisTemplate`. Each template now declares which locations partially reopen when the council reaches a verdict:

| Template | `verdict_reopens` |
|---|---|
| pandemic | `["clinic"]` |
| drought | `["market"]` |
| cyberattack | `["hall"]` |
| election | `[]` |
| crime_wave | `["park"]` |

**Rationale:** A council directive signals institutional intent to act — citizens can return to those locations while the underlying crisis is still technically ongoing. Full resolution (manual `✓ resolve`) still removes the crisis entirely.

#### `api/sim/crisis.py` — `resolved` field + registry methods
- Added `resolved: bool = False` to the `Crisis` dataclass.
- Added `get_crisis(crisis_id)` and `mark_resolved(crisis_id)` to `CrisisRegistry`.

#### `api/sim/engine.py` — Verdict reopening + resolve-by-ID
- `__init__`: Added `_verdict_reopened: set[str] = set()` — tracks locations partially reopened by verdicts.
- `_tick_crisis_effects()`: After rebuilding `_closed_locations` from active templates, subtracts `_verdict_reopened` so verdict-opened locations stay accessible.
- `_apply_verdict_effects()`: After fear reduction and citizen memories, adds `tmpl.verdict_reopens` locations to `_verdict_reopened` and immediately discards them from `_closed_locations`. Logs the partial reopening.
- `resolve_crisis()`: When fully resolving a template, clears that template's `verdict_reopens` entries from `_verdict_reopened` (cleanup), and marks all matching registry crises as resolved.
- **`resolve_crisis_by_id(crisis_id)`** (new method):
  - Not found or already resolved → `None`
  - Has `template_key` → delegates to `resolve_crisis(template_key)` for full world-state effects
  - Template already expired → returns resolution text from template, marks resolved
  - No `template_key` (custom crisis) → generic 15% fear reduction, logs event, adds causal node

#### `api/main.py` — New endpoint + `/crises` enhancement
- **`POST /crisis/id/{crisis_id}/resolve`** — resolves by registry ID. 404 if not found or already resolved.
- **`GET /crises`** — now includes `template_key` and `resolved` per crisis record so the UI can distinguish and filter them.
- Version bumped to `0.7.0`.

---

### Frontend

#### `web/src/panels/RelationshipGraph.tsx` — Force-directed physics layout
Replaced the fixed circular layout with a continuous RAF-based physics simulation:

- **Repulsion**: All node pairs repel each other (`REPULSION = 1400 / dist²`). Prevents overlap, creates natural spacing.
- **Spring forces**: Affinity edges attract (positive) or mildly repel (negative) connected nodes. Ideal distance is shorter for trust edges (55 px) than tension edges (95 px) — trust clusters pull nodes together.
- **Gravity**: Weak constant pull toward canvas centre (0.004) keeps the graph from drifting off-screen.
- **Damping**: Velocity damped by 0.82 each frame — the simulation settles to a stable equilibrium within a few seconds.
- **Initialisation**: New citizens start on the old circle layout; the physics immediately starts moving them into a force-balanced position.
- **Implementation pattern**: All mutable state lives in `useRef` (`physRef`, `citizensRef`, `graphRef`, `selectedIdRef`). The RAF loop starts once on mount (`useEffect([], [])`) and reads from refs — zero re-render overhead per frame.
- Canvas height increased from 200 → 210 px.

**Effect on UX**: Citizen clusters around shared locations or with strong trust bonds visually pull together over time; citizens in tension are pushed apart. The graph is live and never static.

#### `web/src/panels/CouncilChamber.tsx` — Custom crisis resolution UI
- Polls `GET /crises` every 8 seconds and filters for `!template_key && !resolved`.
- Renders an "Custom crises" section above the template presets showing unresolved free-text crises as amber badges with `✓ resolve` buttons.
- Resolve calls `POST /crisis/id/{crisis_id}/resolve`; on success, optimistically removes the badge from the list.
- Template crisis resolve flow is unchanged (still uses `POST /crisis/{key}/resolve`).

---

## Architecture Decisions Made

1. **`_verdict_reopened` as a separate set, not template mutation** — The template objects in `CRISIS_TEMPLATES` are shared singletons. Mutating `closed_locations` in-place would bleed state between simulation instances (test isolation would break). A per-engine `_verdict_reopened` set is clean and reversible.

2. **`resolve_crisis_by_id` delegates to `resolve_crisis` for template crises** — Avoids duplicating the template-removal logic (which is non-trivial: location cleanup, `_verdict_reopened` cleanup, citizen `active_crisis` reset, causal graph node). A single authoritative implementation reduces drift risk.

3. **`resolved` field on `Crisis` rather than a separate registry set** — Keeps the crisis record self-contained for serialisation. The `/crises` endpoint now exposes `resolved` so the frontend can filter without a separate "active crises" endpoint.

4. **RAF loop with empty `useEffect` deps** — The physics loop must not restart on every world-snapshot tick (that would create multiple competing loops and cause jitter). All data it needs is in refs. The empty deps array is intentional and documented with a comment.

5. **Custom crisis fear reduction is 0.15, not 0.30** — Full template resolution drops 0.30 (significant). Custom crises have unknown severity, so 0.15 is conservative and consistent with verdict effects (0.12).

---

## Known Limitations / Next Steps

- **`/crisis/id/{crisis_id}/resolve` route ordering**: FastAPI resolves `/crisis/id/{crisis_id}/resolve` before `/crisis/{template_key}/resolve` because the `id` path segment is more specific. Both endpoints coexist safely. If a template key happened to be literally `"id"` it would shadow this endpoint, but no such template exists.

- **Fine-tuned model**: `ml/train_lora.ipynb` exists; export to GGUF, load into Ollama, wire via `ollama_council_model` in `.env` for a 7B model that speaks in the city's established narrative voice.

- **Deploy**: `cd web && vercel` deploys the frontend. Backend must run locally (Ollama dependency makes cloud hosting non-trivial without GPU).

- **Citizen speech bubbles**: Citizens generate LLM dialogue but it only appears in the Inspector panel. Rendering the last spoken line above each PixiJS sprite (with a timeout fade) would make the city feel alive without any new LLM calls — the `action` field in the snapshot already carries this.

- **Graph legend for force layout**: A short tooltip on hover over a node could show name, occupation, fear, and top relationships — making the force-directed graph interactive beyond just "click to select".

---

## File Change Summary

| File | Change type |
|---|---|
| `api/sim/events.py` | Added `verdict_reopens` field to `CrisisTemplate`; set values on all 5 templates |
| `api/sim/crisis.py` | Added `resolved` field to `Crisis`; added `get_crisis()`, `mark_resolved()` to registry |
| `api/sim/engine.py` | `_verdict_reopened` set; `_tick_crisis_effects` subtraction; `_apply_verdict_effects` reopening; `resolve_crisis` cleanup; new `resolve_crisis_by_id()` |
| `api/main.py` | New `POST /crisis/id/{crisis_id}/resolve`; `/crises` exposes `template_key` + `resolved`; version → 0.7.0 |
| `web/src/panels/RelationshipGraph.tsx` | Full rewrite — RAF physics loop replacing static circle layout |
| `web/src/panels/CouncilChamber.tsx` | Polls `/crises`; custom crisis section with resolve-by-id buttons |
| `api/tests/test_crisis.py` | +6 new tests: resolve-by-id (template, custom, not-found, already-resolved), verdict reopening, cleared on full resolve |

**Test count:** 54 passed (was 48)  
**TypeScript errors:** 0
