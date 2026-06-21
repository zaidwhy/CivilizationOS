# CivilizationOS — Master Build Log
**Phases 0 through 8 | Complete cross-reference with original plan**

> Updated: 2026-06-21 | Version: 0.8.0 | Tests: 54 passing | TS errors: 0

---

## 1. Project Overview

CivilizationOS is a portfolio-grade AI project demonstrating **four required academic pillars** in a single coherent system:

| Pillar | How CivilizationOS delivers it |
|---|---|
| Multi-agent system + domain problem | 10 autonomous citizen-agents (AGORA) + 5 institutional councils × 5 specialist agents (PANTHEON) = **35 agents total** governing a simulated society |
| RAG — novel retrieval | **Temporal-Causal Memory Fusion (TCMF)** — fuses per-agent episodic memory streams with a society-wide causal event graph; not reproducible with any off-the-shelf RAG |
| Fine-tuned model + MLOps | LoRA fine-tune on Qwen2.5 3B (Unsloth, free Colab T4), MLflow run tracking, persona-consistency + debate-quality eval harness |
| Full-stack + Claude API | React + PixiJS isometric city ↔ FastAPI/WebSocket backend; Claude Haiku/Sonnet powers council debates in premium mode |

**Hard constraints from day one:** near-zero budget ($20 cap), Windows 11 laptop, local Ollama, no GPU except free Colab.

---

## 2. System Architecture (as built)

```
civilizationos/
├── api/                        Python 3.12 + FastAPI
│   ├── main.py                 FastAPI app, WebSocket hub, all REST endpoints (v0.7.0)
│   ├── config.py               PREMIUM_MODE, API keys, tier budgets, tick speed
│   ├── sim/
│   │   ├── engine.py           Async tick loop, crisis injection, verdict effects, resolve-by-ID
│   │   ├── world.py            20×15 grid, 10 named locations, day-phase clock (4 phases/day)
│   │   ├── crisis.py           CrisisRegistry — debate transcripts, resolved flag, get/mark methods
│   │   └── events.py           5 crisis templates with fear, location closure, verdict_reopens
│   ├── agents/
│   │   ├── citizen.py          Autonomous citizen (movement, memory, fear, backstory, relationships)
│   │   ├── council.py          5-specialist PANTHEON council with institution lenses
│   │   └── personas.py         10 seed citizens with rich backstory, traits, occupation
│   ├── memory/
│   │   ├── stream.py           Episodic memory stream (relevance × recency × importance scoring)
│   │   ├── causal_graph.py     NetworkX DiGraph: crisis → decision → resolution chain
│   │   ├── tcmf.py             Temporal-Causal Memory Fusion retriever
│   │   └── vectorstore.py      In-process embedding store (L2 cosine, no external DB)
│   └── llm/
│       └── router.py           3-tier router: Ollama (Tier 0) → Gemini (Tier 1) → Claude (Tier 2)
│
├── web/                        React 18 + Vite + TypeScript
│   └── src/
│       ├── App.tsx             Layout, speed slider, spend counter, crisis header pills
│       ├── city/
│       │   ├── CityStage.tsx   PixiJS isometric city (citizens, buildings, crisis visuals, day/night)
│       │   └── iso.ts          Isometric math, palettes, closedLocationColor()
│       ├── panels/
│       │   ├── Inspector.tsx         Citizen mind viewer (memory, relationships, backstory, fear)
│       │   ├── CouncilChamber.tsx    Live debate UI + resolve buttons + custom crisis section
│       │   ├── EventFeed.tsx         City event log (crisis / debate / resolution / conversation)
│       │   ├── RelationshipGraph.tsx Force-directed affinity graph (RAF physics loop)
│       │   ├── Timeline.tsx          Causal event spine (crisis → verdict → resolution)
│       │   └── StatsPanel.tsx        Fear histogram, session counters, memory league table
│       ├── components/
│       │   └── Onboarding.tsx        5-step dismissible first-run tour (localStorage persisted)
│       └── ws/
│           └── store.ts              Zustand store + WebSocket client + health poll
│
└── ml/                         Fine-tuning + MLOps
    ├── train_lora.ipynb         Unsloth LoRA fine-tune on Qwen2.5 3B → GGUF → Ollama
    ├── dataset/                 Synthetic council-voice dataset generator
    ├── evals/                   Persona-consistency + debate-quality eval harness
    └── mlflow/                  Local MLflow tracking store
```

---

## 3. The Novel RAG — Temporal-Causal Memory Fusion (TCMF)

This is the project's primary differentiator. Standard RAG retrieves by semantic similarity alone. TCMF fuses two retrieval layers:

**Layer 1 — Episodic Memory Stream (per citizen):**
Every observation, conversation, reflection, and council decision is a timestamped memory entry with three scores:
- `relevance` = embedding cosine similarity to the query
- `recency` = exponential decay from tick of creation
- `importance` = static weight by kind (observation: 2.0 → conversation: 4.0 → reflection: 6.0 → event: 8.0 → decision: 9.0)

Retrieval score: `α·relevance + β·recency + γ·importance`

Periodic **reflection** (every 240 ticks / one in-world day) synthesises recent memories into higher-level beliefs via LLM.

**Layer 2 — Civic Causal Graph (society-wide):**
A NetworkX directed temporal graph linking `crisis → debate → council decision → resolution → downstream crisis`. Edges carry timestamp and causal weight. `auto_link_predecessors()` automatically connects new events to semantically similar prior events.

**Fusion:**
```
fused_score(memory, query) = episodic_score(memory, query) × (1 + λ × causal_boost(memory))
```
`causal_boost` rewards memories that are semantically close to the **causal ancestors** of the current query event — a witness at the root cause outranks a rumour-holder. When a council deliberates, specialists retrieve the most causally-relevant episodic + institutional precedents and argue using real history.

---

## 4. Cost Architecture — 3-Tier LLM Router

| Tier | Brain | Used for | Per-call cost |
|---|---|---|---|
| **0** | Ollama + Qwen2.5 3B (local) | Citizen conversations, observations, reflections, embeddings (nomic-embed-text) | **$0** |
| **1** | Gemini Flash (free API quota) | Council Historian, Strategist, Skeptic, Predictor turns | **$0** |
| **2** | Claude Haiku 4.5 / Sonnet 4.6 | Council Synthesizer VERDICT turn (premium mode only) | **~$0.002/debate** |

`PREMIUM_MODE=false` → entire app runs at $0. `PREMIUM_MODE=true` → only the final verdict turn hits Claude.  
Running spend tracked live in `/health` → shown in frontend spend counter → full demo costs ~$0.05–0.30.

---

## 5. Phase-by-Phase Build Record

---

### Phase 0 — Foundation
**Duration:** ~2 days | **Planned:** ✅ fully executed

#### What was built

**Backend:**
- `api/config.py` — Pydantic settings: `PREMIUM_MODE`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `SIM_SEED`, `TICK_SECONDS`, `TIER2_BUDGET_USD`. Loaded once with `@lru_cache`.
- `api/llm/router.py` — 3-tier `LLMRouter`:
  - `Tier.LOCAL` → Ollama chat completions
  - `Tier.FREE` → `google-generativeai` SDK (Gemini Flash)
  - `Tier.PREMIUM` → `anthropic` SDK (Claude)
  - Auto-downgrade: if `PREMIUM_MODE=false`, Tier 2 falls back to Tier 1; if Gemini quota exhausted, falls back to Tier 0
  - `router.embed(texts)` → nomic-embed-text via Ollama
  - `router.spend` → running USD spend tracker with budget assertion
- `api/main.py` — FastAPI app skeleton: `/health`, `/ws` WebSocket, CORS middleware for `localhost:5173`
- `api/__init__.py`, `api/sim/__init__.py`, `api/agents/__init__.py`, `api/memory/__init__.py`, `api/llm/__init__.py`

**Frontend:**
- React + Vite + TypeScript scaffold (`web/`)
- `web/src/ws/store.ts` — Zustand store, WebSocket connect, world state subscriber
- Basic `App.tsx` receiving WebSocket ticks and displaying raw JSON

**Tests:**
- `api/tests/test_router.py` — unit tests for all 3 tiers, fallback logic, spend tracking

#### Plan vs reality
The original plan mentioned **ChromaDB** as the vector store. In practice a lighter **in-process vectorstore** (`api/memory/vectorstore.py`) was built instead — no separate ChromaDB server, lower setup friction, zero cost. Functionally equivalent for the project's scale.

---

### Phase 1 — AGORA: Living City
**Duration:** ~1 week | **Planned:** ✅ mostly executed

#### What was built

**Backend:**

`api/sim/world.py`:
- 20×15 isometric grid
- 10 named shared locations: home cluster, Clinic, Market, City Hall, Precinct, Press Building, Park, Trade Exchange, Library, Community Centre
- `DayPhase` enum (NIGHT / MORNING / WORK / EVENING) cycling every 240 ticks
- `clock_label()` → "08:00" style display
- `phase_for_tick()` deterministic time function

`api/agents/personas.py`:
- `Persona` dataclass: `id`, `name`, `age`, `occupation`, `traits`, `sociability`, `home_id`, `workplace_id`
- `SEED_CITIZENS` — 10 fully defined personas: Ava (doctor), Ben (journalist), Cara (trader), Dan (police), Eli (teacher), Finn (lawyer), Grace (cook), Hana (nurse), Ivan (engineer), Jaya (analyst)

`api/agents/citizen.py`:
- `Citizen` wraps a `Persona`; owns `memory`, `relationships`, `fear`, `location_id`, `talk_cooldown`
- `decide_target(world, tick, closed_locations)` — location routing by day phase; routes workers to workplace during WORK phase, home during NIGHT, shared locations otherwise; reroutes around `closed_locations`
- `step()` — one-cell grid movement toward target
- `apply_fear(delta)` / `decay_fear(rate)` / `decay_relationships()`
- `adjust_relationship(other_id, delta)` — ±1 float, clamped; decays 0.5% per tick toward 0
- `snapshot()` → JSON-serialisable dict for WebSocket broadcast

`api/memory/stream.py`:
- `MemoryEntry` dataclass: `text`, `tick`, `kind`, `importance`, `embedding`
- `MemoryStream.add()` — stores by UUID
- `MemoryStream.recent(k)` — last-k by tick
- `MemoryStream.important_since(since_tick, k)` — top-k by importance in window
- `MemoryStream.retrieve(query_emb, alpha, beta, gamma, k)` — TCMF-scored retrieval

`api/memory/vectorstore.py`:
- `VectorStore.add(id, embedding, metadata)`
- `VectorStore.search(query_emb, k)` — L2 cosine, returns `(id, score, metadata)` tuples

`api/sim/engine.py` (Phase 1 core):
- `Engine.__init__` — creates `World`, `citizens`, `CausalGraph`, `TCMFRetriever`, `CrisisRegistry`
- `Engine.advance()` — single async tick: decay fear/relationships, route citizens, record arrivals, maybe spark conversations, trigger end-of-day reflections
- `_start_conversation(a, b, loc, tick)` — adjusts relationship deltas, logs event, spawns LLM task if enabled
- `_llm_converse(a, b, place, tick)` — Tier 0 LLM generates one in-character dialogue line
- `_llm_reflect(c, tick)` — end-of-day reflection prompt (Tier 0); synthesises recent memories into one honest belief sentence
- `snapshot()` → world state dict including citizens, locations, events, clock

`api/main.py` additions:
- `_sim_loop()` — `asyncio.create_task` background loop advancing one tick per `tick_interval`
- `_broadcast_debate_turn()` — pushes `debate_turn` WebSocket messages
- `GET /agent/{agent_id}` — citizen detail (memories, relationships)

**Frontend:**

`web/src/city/CityStage.tsx`:
- PixiJS Application mounted on a `<canvas>`
- Isometric projection: `(col, row) → screen (x, y)`
- Location tiles drawn with occupation-specific palettes (clinic = blue, market = amber, etc.)
- Citizen sprites as coloured circles; move smoothly between grid positions
- Name + occupation label below each citizen

`web/src/city/iso.ts`:
- `toScreen(col, row)` → pixel coordinates
- `LOCATION_COLORS` palette map
- `isoTile()` — draws a single isometric diamond

`web/src/panels/Inspector.tsx`:
- Click citizen → shows name, occupation, age, traits, fear bar
- Lists recent memories with kind badges
- Lists relationships with affinity score

`web/src/panels/EventFeed.tsx`:
- Scrolling log of last 8 events from world snapshot
- Colour-coded by kind (conversation, observation, crisis, etc.)

**Tests added:**
- `api/tests/test_memory_stream.py` — relevance scoring, recency decay, importance ranking
- `api/tests/test_vectorstore.py` — L2 search correctness
- `api/tests/test_engine.py` — determinism (same seed → same positions), work-phase routing, conversation memory formation

#### Plan vs reality
The plan mentioned **speech bubbles** in the PixiJS city. The `action` field was added to citizen snapshots and the engine generates dialogue text, but visual speech bubble rendering above sprites was deferred. Scheduled as Phase 8.

---

### Phase 2 — PANTHEON Councils + TCMF RAG
**Duration:** ~1 week | **Planned:** ✅ fully executed

#### What was built

**Backend:**

`api/memory/causal_graph.py`:
- `CausalGraph` wraps a `networkx.DiGraph`
- `add_event(id, text, tick, kind, institution_id, embedding)` — adds a node with all metadata
- `link(from_id, to_id)` — directed causal edge
- `auto_link_predecessors(event_id)` — finds semantically similar prior events (embedding cosine) and links them as causal ancestors with `causal_weight` proportional to similarity and temporal proximity
- `ancestors_of(event_id, max_hops)` — BFS traversal for context retrieval
- `recent_events(since_tick, k)` — newest-first ordered events
- `__len__` → total node count

`api/memory/tcmf.py`:
- `TCMFRetriever.retrieve(question, citizens, tick, institution_id, crisis_event_id, k, router)`:
  1. Embeds the question
  2. Retrieves top-k memories across all citizens by fused score (relevance × recency × importance)
  3. Finds causal ancestors of `crisis_event_id` in the graph
  4. Boosts memory scores by `causal_boost` if they're semantically near causal ancestors
  5. Returns formatted context string for council prompts

`api/agents/council.py`:
- `DebateTurn` dataclass: `debate_id`, `institution_id`, `role`, `name`, `text`, `tick`, `is_final`
- `COUNCILS` dict mapping institution IDs to `Council` objects
- 5 specialist roles per council: Historian, Strategist, Skeptic, Predictor, Synthesizer
- `Council.deliberate(context, router)` — async generator yielding `DebateTurn` objects
  - Each role has its own system prompt and specific instruction
  - Historian (Tier 1): surfaces causal precedents from TCMF context
  - Strategist (Tier 1): proposes 2 concrete interventions
  - Skeptic (Tier 1): challenges the Strategist, names risks
  - Predictor (Tier 1): probability estimate + worst-case scenario
  - Synthesizer (Tier 2 in premium, Tier 1 fallback): VERDICT in 3-part format

`api/sim/crisis.py`:
- `Crisis` dataclass: `id`, `text`, `tick`, `severity`, `institution_id`, `debate_id`, `causal_event_id`, `template_key`, `resolved`
- `CrisisRegistry`: `create()`, `set_debate_id()`, `add_turn()`, `get_debate()`, `get_crisis()`, `mark_resolved()`, `list_crises()`, `all_debates()`

`api/sim/engine.py` (Phase 2 additions):
- `inject_crisis(text, institution_id, severity, template_key)` — creates `Crisis`, embeds text, adds causal graph node, auto-links predecessors, spawns `_run_debate()`
- `_run_debate(crisis, council, embedding)` — async: retrieves TCMF context, iterates `council.deliberate()`, streams turns via `_on_debate_turn` callback, records verdict as "decision" causal node

`api/main.py` (Phase 2 additions):
- `POST /crisis` — `CrisisRequest { text, institution_id, severity, template_key }`
- `GET /debates/{debate_id}` — full transcript with `complete` flag
- `GET /events/templates` — crisis presets
- `GET /crises` — all registry crises
- `_broadcast_debate_turn` wired to `engine._on_debate_turn`

**Frontend:**

`web/src/ws/store.ts`:
- `DebateTurn` type added
- `debates: Record<debate_id, DebateTurn[]>` state
- `activeDebateId` state — tracks which debate to display
- Handles `"debate_turn"` WebSocket message type

`web/src/panels/CouncilChamber.tsx` (initial version):
- Institution selector dropdown (5 options)
- Crisis text textarea + inject button
- Live streaming debate transcript with role-coloured `TurnCard` components
- Synthesizer verdict highlighted with `★ VERDICT` badge

**Tests added:**
- `api/tests/test_tcmf.py` — TCMF retrieval ordering, causal boost application, context format

---

### Phase 3 — Crises + Society Dynamics
**Duration:** ~1 week | **Planned:** ✅ fully executed

#### What was built

**Backend:**

`api/sim/events.py` — `CrisisTemplate` system:
- `CrisisTemplate` dataclass: `key`, `name`, `description`, `primary_institution`, `secondary_institutions`, `closed_locations`, `base_fear`, `workplace_fear_boost`, `duration_ticks`, `citizen_observation`
- **5 templates** with full world-state effects:
  - `pandemic` → inst_health (primary) + inst_gov (secondary), closes clinic, base_fear 0.5
  - `drought` → inst_economy + inst_gov, closes market, base_fear 0.3
  - `cyberattack` → inst_gov + inst_media + inst_police, closes hall, base_fear 0.35
  - `election` → inst_gov + inst_media, no closures, base_fear 0.2
  - `crime_wave` → inst_police + inst_media, closes park, base_fear 0.4

`api/sim/engine.py` (Phase 3 additions):
- `_active_templates: list[tuple[CrisisTemplate, int]]` — (template, expiry_tick) pairs
- `_closed_locations: set[str]` — rebuilt each tick from active templates
- `_tick_crisis_effects(tick)` — expires templates, rebuilds closed set
- `_apply_template_fear(tmpl, tick)` — applies `base_fear + workplace_boost` to each citizen, injects crisis observation memory
- `inject_crisis()` upgraded — if template exists: appends to `_active_templates`, applies fear, spawns secondary institution debates
- `citizen.decide_target()` upgraded — routes around `_closed_locations`

`api/agents/citizen.py` (Phase 3 additions):
- `active_crisis: str | None` field
- `apply_fear(delta)` — additive, clamped to [0, 1]

**Frontend:**

`web/src/panels/EventFeed.tsx` — upgraded:
- Displays live events from `world.events` (last 8)
- Colour-coded: crisis (red), debate (purple), resolution (green), conversation (blue), observation (grey)

`web/src/panels/RelationshipGraph.tsx` (initial version):
- Canvas-based circle layout of all 10 citizens as coloured nodes
- Edges drawn for citizens sharing a public location (co-location proximity — Phase 6 replaced this)
- Click to select citizen

`api/main.py`:
- `snapshot()` now includes `active_crises` (names list) and `closed_locations`
- Crisis pills appear in App.tsx header

**Tests added:**
- `api/tests/test_crisis.py` — template field validation, pandemic location closure, fear application, secondary institution severity

#### Plan vs reality
The plan mentioned a **Timeline/replay of causal graph** in Phase 3. This was deferred to Phase 5 where it was implemented as the `Timeline.tsx` panel.

---

### Phase 4 — Fine-Tuning + MLOps
**Duration:** ~1 week | **Planned:** ✅ notebook + harness built; model not yet wired into runtime

#### What was built

`ml/train_lora.ipynb`:
- Unsloth + QLoRA fine-tune on Qwen2.5 3B (designed for free Colab T4)
- Training data: synthetic council-voice dataset (distinct tone per role: Historian formal/archival, Strategist assertive/action-oriented, Skeptic adversarial/probing, Predictor probabilistic, Synthesizer decisive/structured)
- Export: GGUF 4-bit quantised → `ollama create civos-council`
- Chat template: alpaca format with council role injection

`ml/dataset/` — dataset generator:
- Generates (crisis_scenario, role, expected_response) triples
- 5 roles × 5 crisis types × N variations = synthetic corpus

`ml/evals/` — eval harness:
- **Persona-consistency score**: measures whether outputs match role vocabulary and tone (rule-based + LLM-judge)
- **Debate-coherence rubric**: checks Historian cites facts, Strategist proposes 2 interventions, Skeptic challenges, Predictor gives probabilities, Synthesizer issues VERDICT
- Gate threshold: model must pass both evals before being eligible for council wiring

`ml/mlflow/` — local MLflow tracking:
- Experiment: `civos-council-lora`
- Logged per run: LoRA rank, learning rate, train loss, eval scores
- Artefacts: checkpoint path, GGUF output path

`api/config.py` (Phase 4 addition):
- `OLLAMA_COUNCIL_MODEL` env var — if set, overrides Tier 0/1 for council turns with the fine-tuned model

#### Plan vs reality
The fine-tuned GGUF model **has not been wired into the live runtime** yet. The `OLLAMA_COUNCIL_MODEL` config hook is in place, but training on free Colab T4 was done in a notebook session outside of this codebase. Wiring it in (once the GGUF is exported and placed in Ollama) is a one-line env var change. This is a Phase 8 candidate.

---

### Phase 5 — Polish, Demo-Readiness
**Duration:** ~3 days | **Planned:** ✅ exceeded (many more items than originally scoped)

#### What was built

**Backend:**

`api/agents/personas.py` — backstory field:
- Added `backstory: str` to `Persona` dataclass
- All 10 citizens given 1–2 sentence personal history explaining their worldview
- Backstory injected into LLM conversation + reflection prompts for consistent in-character voice

`api/agents/citizen.py` — occupation-specific crisis reactions:
- `OCCUPATION_CRISIS_OBSERVATIONS` dict: `occupation → crisis_key → memory text`
- 10 occupations × 3–5 crisis types = **42 distinct first-person reactions**
- `occupation_crisis_observation(crisis_key)` method called at crisis injection time
- `active_crisis` added to `snapshot()`

`api/agents/council.py` — institution lenses:
- `INSTITUTION_LENSES` dict: each institution's 2-line mandate prefix injected into all debate prompts
- Government: law + democratic legitimacy
- Economy: markets + trade + employment + fiscal health
- Healthcare: clinical protocols + resource allocation + epidemiology
- Media: information integrity + counter-disinformation + press freedom
- Police: proportionality + civil rights + community trust
- Role prompt refinements: Historian explicitly not to propose solutions; Skeptic "adversarial but constructive"; Synthesizer 3-part verdict format (action / who / success metric)

`api/sim/events.py`:
- `resolution_text` field on `CrisisTemplate` — message broadcast on manual resolution
- `secondary_severity` field (default 0.7) — secondary institution debates proportionally smaller
- Expanded crisis descriptions to 2 sentences for richer council context

`api/sim/engine.py`:
- `tick_interval: float = 1.0` — mutable (moved from immutable settings) for live speed control
- `resolve_crisis(template_key)` — removes from `_active_templates`, reduces citizen fear by 0.3, clears `active_crisis`, logs resolution event, adds "resolution" causal graph node
- `_run_debate()` — after debate completes, Synthesizer verdict embedded and added to causal graph as "decision" node linked from originating crisis (closes the `crisis → debate → decision` loop)
- `agent_detail()` — includes `backstory`
- `timeline(k)` — new method returning most recent k causal events
- `_llm_converse()` — upgraded with backstory, relationship labels, clearer instruction
- `_llm_reflect()` — upgraded with backstory, crisis context, anti-platitude directive

`api/main.py`:
- `POST /speed { seconds_per_tick }` — sets `engine.tick_interval` (range 0.1–5.0)
- `POST /crisis/{template_key}/resolve` — manual crisis end; 404 if unknown template, 409 if not active
- `GET /timeline?k=60` — causal event history for Timeline panel
- `/health` expanded: `tick_interval`, `causal_events`, `active_crises`, version `0.5.0`

**Frontend:**

`web/src/ws/store.ts`:
- `HealthData` type + `health` state field
- 5-second `pollHealth()` interval started on WebSocket connect
- `Citizen.active_crisis`, `AgentDetail.backstory` added

`web/src/App.tsx`:
- `SpeedControl` — range slider 0.1–3.0 s/tick, POSTs to `/api/speed`
- `SpendCounter` — reads spend from health; green → amber → red gradient; hover tooltip with % used
- Crisis pills with pulsing `crisis-pulse` CSS animation
- `<Onboarding />` + `<Timeline />` added to layout

`web/src/panels/Timeline.tsx` (NEW):
- Polls `/api/timeline?k=40` every 6 seconds
- Vertical event spine with colour-coded nodes: ⚠ crisis (red), ⚖ verdict (amber), ✓ resolution (green), ● other (teal)
- Shows tick number, institution tag, event text (clamped 3 lines)
- Total causal node count in header

`web/src/city/CityStage.tsx` — crisis building visuals:
- Closed locations rendered in desaturated/dark colour via `closedLocationColor()`
- Red ✕ badge circle over closed building
- `⛔` suffix on closed building label
- `drawLocations` called every sync tick (not just on init) so closures update live

`web/src/city/iso.ts`:
- `closedLocationColor(type)` — returns normal colour at 35% brightness

`web/src/panels/CouncilChamber.tsx` — major UX upgrade:
- `<Dots />` animated deliberation indicator (`.` / `..` / `...`)
- Active crisis badges with `✓ resolve` buttons (calls `POST /api/crisis/{key}/resolve`)
- Debate history toggle — shows all past debates, clickable to revisit
- Auto-scroll to bottom as new turns arrive

`web/src/panels/Inspector.tsx` — polish:
- `detail.backstory` rendered in blue-tinted box
- Graduated fear language: uneasy / worried / afraid / terrified (hidden below 10%)
- `♥` / `⚡` icons on relationships
- Tick number + importance in memory list

`web/src/components/Onboarding.tsx` (NEW):
- 5-step dismissible overlay: Welcome → City Map → Council Panel → TCMF concept → Speed & Cost
- `localStorage` persistence under `civOS_onboarding_done_v1`
- Animated step dots, skippable at any point

`web/src/index.css`:
- `crisis-pulse` keyframe animation
- Styled range slider thumb (cross-browser)
- 4px styled scrollbars
- Spacing polish

`README.md` — full rewrite: architecture tree, quick-start, API reference table, cost breakdown, 4 pillars table, demo walkthrough

#### Plan vs reality
- ✅ Visual polish, onboarding tour, speed control, cost counter — all done (and more)
- ❌ **"Rewind story" feature** — not implemented (not in any handoff, no timeline scrubbing)
- ❌ **Demo video recording** — noted in plan but no video artefact in repo
- ❌ **Vercel deploy** — frontend deployable but not yet deployed

---

### Phase 6 — Verdict Effects, Real Relationship Graph, Stats Panel
**Duration:** ~1 day | **Not in original plan** — added as Phase 5 limitations resolved

#### What was built

**Backend:**

`api/sim/events.py`:
- `verdict_fear_reduction: float = 0.12` — field on `CrisisTemplate`; controls how much fear drops when council delivers a verdict (vs 0.3 for full resolution)

`api/sim/crisis.py`:
- `template_key: str | None` — added to `Crisis` dataclass (connects a live crisis back to its originating template for verdict effects)
- `CrisisRegistry.create()` — now accepts and stores `template_key`

`api/sim/engine.py`:
- `inject_crisis()` — passes `template_key` to `crises.create()`
- `_run_debate()` — after verdict written to causal graph, checks `crisis.template_key` and calls `_apply_verdict_effects(tmpl, verdict_text)` if template exists
- `_apply_verdict_effects(tmpl, verdict_text)` (new method):
  - Reduces all citizens' fear by `tmpl.verdict_fear_reduction`
  - Adds "decision" kind memory to every citizen: `"Council issued directive on {name}: {first 100 chars of verdict}"`
  - Logs a "decision" event — councils are now **historically aware**: future crises retrieve prior verdicts as causal ancestors

`api/main.py`:
- `GET /graph` — returns `{ nodes: [{id, name, occupation, fear}], edges: [{source, target, weight, positive}] }`. Deduplicates edge pairs; filters to `|weight| > 0.05` threshold.
- `GET /stats` — returns fear histogram (5 buckets × 20% bands), `avg_fear`, `memory_counts` per citizen, `total_debates`, `active_crises`, `causal_events`, `tick`
- Version → `0.6.0`

**Frontend:**

`web/src/panels/RelationshipGraph.tsx` — real affinity edges:
- Polls `GET /api/graph` every 6 seconds
- Green edges = positive affinity (trust); red = negative (tension)
- Edge thickness scales with `|weight| × 3`; opacity with `|weight| × 1.5` (capped 0.9)
- While loading: falls back to faint co-location lines
- Legend updated: "trust · tension"
- Edge count badge (hidden when 0)

`web/src/panels/StatsPanel.tsx` (NEW):
- Polls `GET /api/stats` every 5 seconds
- **Fear Histogram**: Canvas bar chart, 5 buckets, colour-coded green→amber→red, count labels
- **Session Counters**: 3-cell grid showing debates / causal nodes / active crises
- **Memory League Table**: horizontal bar chart of memories per citizen sorted descending, purple bars
- Returns `null` until first fetch (prevents layout flicker)
- Tick number footer

`web/src/App.tsx`:
- `<StatsPanel />` imported and placed below `<Timeline />` in sidebar

---

### Phase 7 — Crisis-by-ID Resolution, Verdict Reopening, Force-Directed Graph
**Duration:** ~1 day | **Not in original plan** — added to close Phase 6 limitations

#### What was built

**Backend:**

`api/sim/events.py`:
- `verdict_reopens: list[str]` — new field on `CrisisTemplate`; locations partially reopened when council delivers verdict
- All 5 templates updated:
  - pandemic: `verdict_reopens=["clinic"]`
  - drought: `verdict_reopens=["market"]`
  - cyberattack: `verdict_reopens=["hall"]`
  - election: `verdict_reopens=[]`
  - crime_wave: `verdict_reopens=["park"]`

`api/sim/crisis.py`:
- `resolved: bool = False` — new field on `Crisis` dataclass
- `CrisisRegistry.get_crisis(crisis_id)` — lookup by ID
- `CrisisRegistry.mark_resolved(crisis_id)` — sets `resolved = True`

`api/sim/engine.py`:
- `_verdict_reopened: set[str]` — new per-engine set tracking locations partially reopened by verdicts
- `_tick_crisis_effects()` — after rebuilding `_closed_locations`, subtracts `_verdict_reopened` so verdict-opened locations stay accessible across ticks
- `_apply_verdict_effects()` — adds `tmpl.verdict_reopens` entries to `_verdict_reopened` and immediately discards from `_closed_locations`; log message includes partial reopening note
- `resolve_crisis()` — now clears `_verdict_reopened` entries for the resolved template (cleanup); marks all matching registry crises as `resolved = True`
- `resolve_crisis_by_id(crisis_id)` (new method):
  - Not found or already resolved → `None`
  - Has `template_key` → delegates to `resolve_crisis(template_key)` for full world-state effects
  - Template already expired → returns `resolution_text` from template, marks resolved
  - No `template_key` (custom free-text crisis) → generic 15% fear reduction + causal graph node + marks resolved

`api/main.py`:
- `POST /crisis/id/{crisis_id}/resolve` — resolve any crisis by registry ID; 404 if not found or already resolved
- `GET /crises` — now includes `template_key` and `resolved` per record
- Version → `0.7.0`

**Frontend:**

`web/src/panels/RelationshipGraph.tsx` — full rewrite to force-directed physics:
- **Single RAF loop** started once on mount (`useEffect([], [])`) — never restarts on re-render
- All mutable state in `useRef` (physRef, citizensRef, graphRef, selectedIdRef) — zero React overhead per frame
- Physics per frame:
  - **Repulsion** `REPULSION=1400/dist²` between all node pairs
  - **Spring forces** along affinity edges: `SPRING_STRENGTH=0.05 × |weight| × (dist - ideal_dist)`; ideal distance 55 px for trust, 95 px for tension
  - **Centre gravity** `0.004 × displacement` keeps graph from drifting
  - **Velocity damping** `×0.82` per frame → simulation settles in ~3 seconds
- New citizen nodes initialised on circle; physics immediately moves them to force-balanced positions
- Trust bond clusters visually pull together; tension edges push apart
- Canvas height 200 → 210 px

`web/src/panels/CouncilChamber.tsx`:
- Added `CrisisRecord` type
- Polls `GET /crises` every 8 seconds; filters for `!template_key && !resolved`
- "Custom crises" section above template presets — amber badges with `✓ resolve` buttons
- `resolveById(crisisId)` — calls `POST /crisis/id/{crisisId}/resolve`; optimistically removes badge on success

**Tests added (6 new):**
- `test_resolve_template_crisis_by_id` — template crisis resolved by ID, removed from active templates, marked resolved in registry
- `test_resolve_custom_crisis_by_id` — free-text crisis resolved by ID, marked resolved
- `test_resolve_by_id_not_found_returns_none` — non-existent ID returns None
- `test_resolve_by_id_already_resolved_returns_none` — already-resolved ID returns None
- `test_verdict_reopens_location` — apply verdict effects on pandemic → clinic leaves `_closed_locations`, enters `_verdict_reopened`; stays open on subsequent tick
- `test_verdict_reopened_cleared_on_full_resolve` — full resolve clears `_verdict_reopened`

---

## 6. Original Plan vs Reality — Cross-Reference Table

| Item from original plan | Status | Notes |
|---|---|---|
| Monorepo scaffold, venv, Vite, `.env` | ✅ Done | |
| Ollama + Qwen2.5 3B + nomic-embed-text | ✅ Done | |
| 3-tier LLM router with PREMIUM_MODE | ✅ Done | |
| FastAPI + WebSocket → React ticks | ✅ Done | |
| ChromaDB for vector store | ⚠ Changed | Built in-process `vectorstore.py` instead — lighter, zero setup friction, same interface |
| World clock, locations, async tick loop | ✅ Done | |
| Citizen perceive→plan→act→converse | ✅ Done | |
| Memory stream + reflection loop | ✅ Done | |
| PixiJS isometric city | ✅ Done | |
| **Speech bubbles above sprites** | ❌ Not done | `action` field exists in snapshot; rendering deferred to Phase 8 |
| WebSocket world state → Zustand | ✅ Done | |
| 10 citizens live a day (milestone) | ✅ Done | 48 then 54 tests verify it |
| Causal graph (causal_graph.py) | ✅ Done | |
| TCMF fusion retriever (tcmf.py) | ✅ Done | Novel RAG fully operational |
| 5-specialist council debate | ✅ Done | |
| CouncilChamber UI | ✅ Done | Much richer than planned |
| Trigger decision, watch agents argue (milestone) | ✅ Done | |
| 5 crisis templates | ✅ Done | pandemic / drought / cyberattack / election / crime_wave |
| Cross-institution effects + citizen reactions | ✅ Done | Occupation-specific, 42 distinct reactions |
| EventFeed UI | ✅ Done | |
| RelationshipGraph | ✅ Done (Phase 6/7 enhanced) | Started as co-location; upgraded to affinity + force-directed layout |
| **Timeline / causal replay** | ✅ Done | Done in Phase 5 (deferred from Phase 3) |
| Inject pandemic → councils → city reacts (milestone) | ✅ Done | |
| LoRA fine-tune notebook (Colab) | ✅ Done | `ml/train_lora.ipynb` exists |
| Synthetic council-voice dataset | ✅ Done | |
| MLflow tracking | ✅ Done | Local tracking store |
| Eval harness (persona + debate quality) | ✅ Done | |
| **Fine-tuned model wired into councils** | ❌ Not done | `OLLAMA_COUNCIL_MODEL` config hook ready; needs GGUF exported and loaded |
| Fine-tuned model passes evals (milestone) | ⚠ Partial | Harness built; model not yet evaluated in live loop |
| Visual polish | ✅ Done | |
| Onboarding tooltip tour | ✅ Done | 5-step, localStorage-persisted |
| **"Rewind story" feature** | ❌ Not done | Never implemented |
| README + architecture diagram | ✅ Done | Full rewrite in Phase 5 |
| **Demo video recording** | ❌ Not done | No video artefact in repo |
| **Deploy frontend to Vercel** | ❌ Not done | Frontend deployable (`vercel` command), not yet pushed |
| Speed control | ✅ Done (Phase 5) | Slider + `/speed` endpoint |
| Verdict → causal graph | ✅ Done (Phase 5) | |
| Verdict → world-state effects | ✅ Done (Phase 6) | Fear reduction + citizen memories |
| Verdict → location reopening | ✅ Done (Phase 7) | `verdict_reopens` on templates |
| Real affinity relationship graph | ✅ Done (Phase 6) | |
| Force-directed graph layout | ✅ Done (Phase 7) | |
| Stats panel | ✅ Done (Phase 6) | Fear histogram, counters, memory league |
| Custom crisis resolution by ID | ✅ Done (Phase 7) | `POST /crisis/id/{id}/resolve` |

---

## 7. What Remains — Phase 8 Candidates

### High impact, in-code (recommended for Phase 8)

**A. Citizen speech bubbles in PixiJS**
- The `action` field in every citizen's world snapshot already carries the last spoken line or movement description.
- Render this as a floating text label above the PixiJS sprite, with a 5-second fade-out timer.
- Zero new LLM calls. Pure rendering work. Makes the city feel dramatically alive.
- Files to touch: `web/src/city/CityStage.tsx`, `web/src/city/iso.ts`

**B. Social graph hover tooltip**
- The force-directed graph is live but only supports click-to-select.
- On hover over a node: show a small tooltip with name, occupation, fear %, and top 3 relationships by affinity.
- Files to touch: `web/src/panels/RelationshipGraph.tsx`

**C. Sixth crisis template**
- Ideas: **Housing Crisis** (inst_economy), **Food Riot** (inst_police + inst_economy), **Power Outage** (inst_gov)
- Files to touch: `api/sim/events.py` (add template), potentially new occupation observations in `citizen.py`

### Requires external setup

**D. Wire fine-tuned model**
- Export the trained LoRA from `ml/train_lora.ipynb` to GGUF
- `ollama create civos-council -f <modelfile>`
- Set `OLLAMA_COUNCIL_MODEL=civos-council` in `.env`
- `PREMIUM_MODE=false` councils will use the fine-tuned voice

**E. Deploy frontend to Vercel**
- `cd web && vercel` — one command
- Backend must run locally (Ollama dependency)
- Add `VITE_API_BASE_URL` env var for the Vercel build pointing to local/ngrok backend

---

## 8. Test Coverage Summary

| Test file | Coverage area | Count |
|---|---|---|
| `test_engine.py` | Tick determinism, citizen routing, conversations, snapshot shape | 5 |
| `test_memory_stream.py` | TCMF scoring, recency decay, importance ranking, reflection | 7 |
| `test_vectorstore.py` | L2 cosine search correctness | 7 |
| `test_router.py` | 3-tier routing, downgrade logic, spend tracking | 9 |
| `test_tcmf.py` | TCMF retrieval ordering, causal boost, context format | 10 |
| `test_crisis.py` | Templates, fear, location closure, resolve-by-ID, verdict reopening | 16 |
| **Total** | | **54 passed** |

---

## 9. API Endpoints — Complete Reference (v0.7.0)

| Method | Path | Description | Added |
|---|---|---|---|
| GET | `/health` | Status, version, spend, tick interval, brains | Phase 0 |
| GET | `/agent/{id}` | Citizen detail: memories, relationships, backstory | Phase 1 |
| WS | `/ws` | Live world snapshots + debate turn stream | Phase 0 |
| GET | `/llm/ping?tier=0` | Smoke-test a specific LLM tier | Phase 0 |
| POST | `/crisis` | Inject crisis (triggers council debate) | Phase 2 |
| GET | `/crises` | All registry crises with template_key + resolved | Phase 2 / Phase 7 |
| GET | `/debates/{id}` | Full debate transcript | Phase 2 |
| GET | `/events/templates` | All 5 crisis template presets | Phase 2 |
| GET | `/timeline?k=60` | Causal event history newest-first | Phase 5 |
| POST | `/speed` | Set tick interval 0.1–5.0 s | Phase 5 |
| POST | `/crisis/{key}/resolve` | Resolve active crisis by template key | Phase 5 |
| GET | `/graph` | Social graph: nodes + weighted affinity edges | Phase 6 |
| GET | `/stats` | Fear histogram, debate count, memory counts | Phase 6 |
| POST | `/crisis/id/{id}/resolve` | Resolve any crisis by registry ID | Phase 7 |

---

## 10. Key Design Decisions (cross-phase)

| Decision | Where | Why |
|---|---|---|
| In-process vectorstore instead of ChromaDB | Phase 0 | Zero setup, deterministic, scales fine for 10 citizens × 200 memories |
| Event-driven LLM calls (not every tick) | Phase 1 | Single biggest cost saver — idle walking never touches the LLM |
| `tick_interval` on Engine, not Settings | Phase 5 | Settings frozen by `@lru_cache`; mutable speed control needs a live attribute |
| `template_key` nullable on Crisis | Phase 6 | Custom free-text crises have no template; verdict effects should not fire for unknown severities |
| `/graph` edge threshold `|weight| > 0.05` | Phase 6 | Prevents near-zero transient edges from cluttering the graph |
| `_verdict_reopened` as separate set | Phase 7 | Templates are shared singletons; mutating `closed_locations` in-place would break test isolation |
| RAF loop with empty deps | Phase 7 | Physics loop must not restart on every world-snapshot tick — empty deps is intentional |
| `resolve_crisis_by_id` delegates to `resolve_crisis` | Phase 7 | Avoids duplicating template removal logic (fear, closed locations, causal graph, citizen reset) |
| Custom crisis fear reduction 0.15 (not 0.30) | Phase 7 | Unknown severity warrants conservative default; 0.30 is reserved for full template resolution |
