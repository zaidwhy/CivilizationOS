# CivilizationOS — Phase 5 Handoff Log

**Date:** 2026-06-20  
**Phase:** 5 — Polish, refinement, and demo-readiness  
**Branch:** main  
**Tests:** 48 passed, 0 failed  
**TypeScript:** 0 errors  

---

## What Was Built in Phase 5

### Backend

#### `api/agents/personas.py` — Rich Backstory Personas
Added `backstory: str` field to the `Persona` dataclass. Each of the 10 citizens now has a 1-2 sentence personal history that explains *why* they think the way they do. This backstory is injected into LLM conversation and reflection prompts, making each citizen's dialogue distinctly in-character even under crisis pressure.

Examples:
- **Ava** (doctor): *"Ran the ER through the last flu season — lost two patients to delayed care."*
- **Ben** (journalist): *"Broke the City Hall procurement scandal five years ago. Officials still don't return his calls."*
- **Iris** (analyst): *"Built the Trade Exchange's anomaly-detection model in her first month."*

#### `api/agents/citizen.py` — Occupation-Specific Crisis Reactions
Added `OCCUPATION_CRISIS_OBSERVATIONS` dict mapping `occupation → crisis_key → specific memory text`. When a crisis template fires, each citizen now gets a memory that reflects their professional lens rather than the generic observation text.

10 occupations × 3-5 crisis types = 42 distinct first-person crisis reactions.

Added `occupation_crisis_observation(crisis_key)` method. Added `active_crisis` to `snapshot()` so the frontend can display it.

#### `api/agents/council.py` — Institution-Specific Debate Lenses
Added `INSTITUTION_LENSES` dict. Each council's debate prompt is now prefixed with its institutional mandate:
- Government: law, constitutional authority, public trust
- Economy: markets, trade, employment, fiscal health  
- Healthcare: clinical protocols, resource allocation, epidemiology
- Media: information integrity, counter-disinformation, press freedom
- Police: proportionality, civil liberties, community trust

Increased `max_tokens` from 180 → 200. Role prompts refined: Historian explicitly told not to propose solutions, Skeptic told to be "adversarial but constructive", Synthesizer now specifies the 3-part verdict format (action / who / success metric).

#### `api/sim/events.py` — Richer Crisis Templates
Added `resolution_text` field to `CrisisTemplate` — the message broadcast when a crisis is manually resolved. Added `secondary_severity` field (default 0.7) so secondary institution debates are proportionally smaller. Expanded crisis descriptions from one sentence to 2 sentences for richer council context.

#### `api/sim/engine.py` — Speed Control + Crisis Resolve + Verdict Graph
- **`tick_interval: float = 1.0`** — mutable attribute (was reading from immutable settings), used by `_sim_loop` in main.py. Enables live speed control.
- **`resolve_crisis(template_key)`** — removes a crisis template from `_active_templates`, cools citizen fear by 0.3, clears `active_crisis` on affected citizens, logs a resolution event, and adds a "resolution" node to the causal graph.
- **Verdict → causal graph** — after `_run_debate` completes, the Synthesizer's verdict text is embedded (if LLM available) and added to the causal graph as a `"decision"` node linked from the originating crisis node. This closes the loop: `crisis → debate → decision → (possible downstream crisis)`.
- **`agent_detail()`** — now includes `backstory` in the returned dict.
- **`timeline(k)`** — new method returning the most recent k causal graph events, used by `/timeline` endpoint.
- **`_apply_template_fear()`** — upgraded to call `occupation_crisis_observation()` first; falls back to generic `citizen_observation` only if occupation-specific text is unavailable.
- **Improved LLM prompts** — `_llm_converse` now includes `backstory`, richer relationship labels (trusted / met before / tension), and clearer instruction. `_llm_reflect` includes backstory and a prompt against "generic platitudes".

#### `api/main.py` — Three New Endpoints
- `POST /speed` — `{ "seconds_per_tick": float }` → sets `engine.tick_interval`. Range 0.1–5.0.
- `POST /crisis/{template_key}/resolve` — manually resolves an active crisis. 404 if unknown template, 409 if not currently active.
- `GET /timeline?k=60` — returns `{ events, total_nodes }` for the Timeline panel.

Updated `/health` to include `tick_interval`, `causal_events`, `active_crises`, and `version: "0.5.0"`.

Updated `/events/templates` to include `resolution_text` per template.

Updated `_sim_loop` to use `engine.tick_interval` instead of `settings.tick_seconds`.

---

### Frontend

#### `web/src/ws/store.ts` — Health Polling + Speed State
- Added `HealthData` type and `health: HealthData | null` state field.
- `connectWorldSocket()` now also starts a 5-second health poll (`pollHealth`). Called once immediately on connect.
- `Citizen` type now includes `active_crisis: string | null`.
- `AgentDetail` now includes `backstory: string`.

#### `web/src/App.tsx` — Speed Slider + Dynamic Spend Counter
- **`SpeedControl`** component: range slider 0.1–3.0 seconds/tick. POSTs to `/api/speed` on change. Reads initial value from `health.tick_interval`.
- **`SpendCounter`** component: reads from `health`. Shows `free · $0.000` in green, turning amber at 50% budget and red at 80%. Hover tooltip shows exact percentage. Shows `premium ⚡` badge when premium mode is active.
- Crisis pills in the header now use `crisis-pill` CSS class for the pulsing animation.
- Added `<Onboarding />` and `<Timeline />` to the layout.

#### `web/src/panels/Timeline.tsx` — NEW Causal Timeline Panel
Polls `/api/timeline?k=40` every 6 seconds. Renders a vertical spine with colour-coded nodes per event kind:
- Red `⚠` = crisis
- Amber `⚖` = council decision (verdict)
- Green `✓` = resolution
- Teal `●` = other events

Each node shows tick number, institution tag, and the event text (clamped to 3 lines). Shows total graph node count in the header.

#### `web/src/city/CityStage.tsx` — Crisis Visual Effects
- Closed locations are now rendered in a darkened/desaturated colour (via `closedLocationColor()` from `iso.ts`).
- Closed buildings show a red `✕` badge in a dark circle overlay.
- Labels of closed buildings show `⛔` suffix in red.
- `drawLocations` is now called every sync tick (not just on first build) so closures update live.
- Fixed stale `(bubble as any)._bg` cast to proper typed cast.

#### `web/src/city/iso.ts` — `closedLocationColor`
Added `closedLocationColor(type)` — returns the location's normal colour at 35% brightness for the "closed" state visual.

#### `web/src/panels/CouncilChamber.tsx` — Major UX Upgrade
- **Animated `<Dots />`** component cycling `.` / `..` / `...` while debate is in progress.
- **Active crisis badges** now include a **✓ resolve** button per active crisis, calling `POST /api/crisis/{key}/resolve`.
- **Debate history** toggle: when more than 1 debate exists, a "history (N)" button appears. History view shows all debates with a clickable list; clicking returns to current view showing that debate.
- **Auto-scroll** to bottom as new turns arrive (via `useRef` + `scrollIntoView`).
- `resolution_text` fetched from templates, shown in resolve button tooltip.

#### `web/src/panels/Inspector.tsx` — Backstory + Better Fear
- Renders `detail.backstory` in a subtle blue-tinted box below the name.
- Fear label now uses graduated human language: "uneasy" / "worried" / "afraid" / "terrified" (hidden below 10%).
- Relationships show `♥` or `⚡` icon prefix.
- Memory list shows tick number alongside kind and importance.

#### `web/src/components/Onboarding.tsx` — NEW First-Run Tour
5-step dismissible overlay covering: Welcome, City Map, Council Panel, TCMF concept, Speed & Cost. Dismissed state persisted in `localStorage` under key `civOS_onboarding_done_v1`. Step progress shown as animated dots. Skippable at any point.

#### `web/src/index.css` — Polish Pass
- `crisis-pulse` keyframe animation for active crisis pills.
- Styled range slider thumb (cross-browser).
- Styled scrollbars (4px, subtle).
- Minor spacing tightening throughout.

---

## Architecture Decisions Made

1. **`tick_interval` on Engine, not Settings** — `get_settings()` uses `@lru_cache`, so the returned object is immutable at runtime. Moving `tick_interval` to `Engine` as a plain mutable float was the correct fix.

2. **Verdict as causal graph node** — adds "decision" node kind to the existing graph taxonomy (crisis / event / resolution). This is the key causal loop closure: future crises in the same domain will now see prior verdicts as ancestors in TCMF retrieval, making councils historically aware across sessions.

3. **Occupation-specific reactions at crisis injection time** — applied in `_apply_template_fear()` rather than lazily. This means all 10 citizens immediately build distinct professional memories on injection, giving the council richer TCMF context when it deliberates.

4. **`drawLocations` called every sync** — the location layer is cheap to rebuild (no textures, pure vector). Rebuilding every tick ensures closures appear/disappear instantly without a diffing mechanism.

5. **`/timeline` polls on a 6s interval** — longer than the health poll (5s) to avoid stacking network requests. The causal graph grows slowly relative to the tick rate.

---

## Known Limitations / Next Steps

- **Crisis resolution UX**: The resolve button appears only if the template key matches a loaded template name. If a custom (non-template) crisis is injected, no resolve button appears. A `POST /crisis/{crisis_id}/resolve` by crisis ID (not template key) would fix this.
- **Relationship graph**: Currently shows co-location edges only (no affinity weights). A proper implementation would fetch per-citizen relationships from `/agent/{id}` for all citizens on a slow poll.
- **Council verdict effects**: The verdict text is logged to the causal graph but does not yet programmatically mutate world state (e.g., "open the clinic" after a pandemic verdict). Adding a verdict parser that applies structured effects would close this loop.
- **Fine-tuned model**: `ml/train_lora.ipynb` exists; the model can be exported to GGUF, loaded into Ollama, and wired via `ollama_council_model` in `.env`. Once done, `PREMIUM_MODE=false` councils will use the fine-tuned voice.
- **Deploy**: Frontend can be deployed to Vercel (`cd web && vercel`). The backend must run locally because Ollama lives on the laptop; only the frontend is statically deployable.

---

## File Change Summary

| File | Change type |
|---|---|
| `api/agents/personas.py` | Added `backstory` field, rewrote all 10 persona descriptions |
| `api/agents/citizen.py` | Added `OCCUPATION_CRISIS_OBSERVATIONS`, `occupation_crisis_observation()`, updated snapshot |
| `api/agents/council.py` | Added `INSTITUTION_LENSES`, refined all role system prompts, increased token limits |
| `api/sim/events.py` | Added `resolution_text`, `secondary_severity`, expanded descriptions |
| `api/sim/engine.py` | `tick_interval`, `resolve_crisis()`, verdict→causal graph, improved LLM prompts, `timeline()` |
| `api/main.py` | New `/speed`, `/crisis/{key}/resolve`, `/timeline` endpoints; updated `/health`, `_sim_loop` |
| `web/src/ws/store.ts` | Added `HealthData`, health poll, `active_crisis` on Citizen, `backstory` on AgentDetail |
| `web/src/App.tsx` | `SpeedControl`, `SpendCounter`, `<Onboarding>`, `<Timeline>`, crisis-pill CSS |
| `web/src/panels/Timeline.tsx` | **NEW** — causal event timeline panel |
| `web/src/panels/CouncilChamber.tsx` | `<Dots>`, resolve buttons, debate history view, auto-scroll |
| `web/src/panels/Inspector.tsx` | Backstory display, graduated fear labels, relationship icons |
| `web/src/components/Onboarding.tsx` | **NEW** — 5-step dismissible first-run tour |
| `web/src/city/CityStage.tsx` | Crisis building visuals (darkened + ✕ badge + ⛔ label), type fixes |
| `web/src/city/iso.ts` | Added `closedLocationColor()` |
| `web/src/index.css` | `crisis-pulse` animation, slider styles, scrollbar, polish |
| `README.md` | Full rewrite — architecture, quick-start, API reference, cost breakdown, pillars |
