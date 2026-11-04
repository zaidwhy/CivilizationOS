# Architecture

System-design case study for CivilizationOS. `DESIGN.md` covers the visual design
language (color, type, layout); this document covers the system.

## Problem

Simulate a small society of autonomous agents whose behaviour and memory are causally
consistent: when a crisis happens, the agents and councils that respond should be able
to recall not just "similar" past events but the actual chain of cause and effect that
led here, and a visitor should be able to inject a crisis and watch the society react in
real time, on a laptop, for close to $0.

## Requirements

- Tick a society of 10 citizens with routines, conversations, relationships, and
  episodic memory, visible live over a WebSocket to any number of browser tabs.
- Run five-role structured council debates on demand when a crisis is injected, using
  retrieval that favours causally relevant memories over merely similar-sounding ones.
- Run at $0 in local development and at near-$0 on a public demo deploy.
- Be benchmarkable: the retrieval method (TCMF) must be measurable against baselines,
  not just demoed.

## Constraints

- Free hosting: Render's free web-service tier (sleeps after ~15 min idle, no
  persistent disk, 750 instance-hours/month per account) and Vercel's hobby tier for
  the static frontend.
- Ollama (the $0 local model tier) is not reachable from Render, so the cloud deploy
  cannot run the always-on ambient loop (citizen small talk, reflection, emergent
  crises) the way local development does - `DEMO_MODE=true` turns that loop off on the
  public deploy while crisis injection and council debates stay fully live.
- A single Python process holds all simulation state in memory; there is no database
  server. Restarting the process loses the running society (a demo, not a durable
  service).

## Architecture

```
Browser (React + Three.js)  <-- WebSocket (state broadcast) + REST (crisis/timeline/graph)
        |
FastAPI process (api/main.py)
   |-- Engine (api/sim/engine.py): async tick loop, one Python process, one asyncio task
   |     |-- World (api/sim/world.py): 20x15 grid, 10 named locations, day-phase clock
   |     |-- Citizens (api/agents/citizen.py): movement, conversation, fear, backstory
   |     |-- Councils (api/agents/council.py): 5-role structured debate per institution
   |     |-- CausalGraph (api/memory/causal_graph.py): NetworkX DiGraph, crisis -> decision -> outcome
   |     `-- TCMF (api/memory/tcmf.py): fuses episodic memory with causal-graph proximity
   |-- LLMRouter (api/llm/router.py): 3-tier routing (Ollama -> Gemini -> Claude/OpenRouter)
   `-- VectorStore (api/memory/vectorstore.py): in-process embedding store, no external DB
```

Everything runs inside one FastAPI process. There is no message queue, no separate
worker, no external database - state lives in Python objects owned by the `Engine`
instance created once at process start (`api/main.py`), and every request or WebSocket
message reads or mutates that same instance.

## Data flow: injecting a crisis

1. `POST /crisis` (public, rate-limited: 30s cooldown + a per-UTC-day cap) validates the
   institution and template, then calls `Engine.inject_crisis()`.
2. The crisis becomes a node in the `CausalGraph`, linked to whatever prior events (a
   drought, an election, an earlier unresolved crisis) plausibly caused it.
3. `TCMF.retrieve()` is called per-citizen-role in the debate: it scores each citizen's
   episodic memories by the generative-agents formula (relevance x recency x
   importance), separately walks the causal graph backward from the crisis to find
   ancestor events, and combines the two as
   `normalize(episodic_score) + lambda * causal_boost` - additive, not multiplicative,
   specifically so a memory that is semantically distant from the crisis but causally
   upstream of it can still surface (see `api/memory/tcmf.py`'s module docstring and
   `research/tcmf_paper/FINDINGS.md` F3-F7 for the benchmarked reason the earlier
   multiplicative version failed).
4. The five council roles (Historian, Strategist, Skeptic, Predictor, Synthesizer) each
   get the fused context and run in sequence through `Engine._run_debate()`, calling
   `LLMRouter.complete()` per turn.
5. Each turn is broadcast over the WebSocket as it completes, so the browser shows the
   debate live rather than waiting for the verdict.
6. The Synthesizer's verdict is applied back into the simulation (fear levels, faction
   state) and logged as a new causal-graph node, closing the loop for the next crisis.

## Data flow: what a visitor sees

The browser holds one Zustand store (`web/src/ws/store.ts`); everything on screen reads it.

```
WebSocket "world" message (every tick)  ──►  store.world
        │                                       │
        │                       ┌───────────────┼──────────────────────┐
        │                       ▼               ▼                      ▼
        │             CityStage3D.tsx     Narrator.tsx           Details drawer
        │             draws the town,     narration.ts rules:    (panels, REST:
        │             people, cordons     event -> one sentence  /agent, /timeline,
        │                                 + store.focus          /stats, ...)
        │                                       │
        │             camera glides to  ◄───────┘  store.focus = { location | citizen }
```

1. `Engine.snapshot()` sends the whole visible world each tick: locations (including one
   home per citizen), citizens with position and fear, closed buildings, and the last 8
   events from the log.
2. `CityStage3D` rebuilds nothing per tick except people's targets; buildings are built
   once from the first snapshot. People glide to their spot and walk while moving; the
   ring under each person is their fear (green, amber, red).
3. `Narrator` matches events by identity (`tick|kind|text`), not by tick, because the
   engine stamps a crisis or verdict with a tick the client has already received.
   `narration.ts` turns each new event into at most one sentence with a weight (crisis
   and verdict 3, debate and fear 2, social 1, chatter 0) and a topic; a queued line with
   the same topic is replaced, so a debate or a wave of fear stays one line.
4. The narrator shows the heaviest waiting line for at least 6.5 s and sets
   `store.focus`; the stage moves the camera there unless the visitor has dragged it in
   the last 15 s. With nothing live to say, a short tour alternates with who is talking.

## Components

| Component | File | Responsibility |
|---|---|---|
| Engine | `api/sim/engine.py` (786 lines) | owns the tick loop, crisis lifecycle, faction detection (union-find over relationship affinity), council track record |
| World | `api/sim/world.py` | grid, locations, day-phase clock |
| Citizen | `api/agents/citizen.py` | one agent's movement, memory, occupation-specific crisis reactions |
| Council | `api/agents/council.py` | the 5-role debate structure and institution lens (law, markets, clinical protocol, information integrity, civil rights) |
| CausalGraph | `api/memory/causal_graph.py` | temporal causal edges between events; cosine similarity helper |
| TCMF | `api/memory/tcmf.py` | the fused retrieval scorer described above |
| LLMRouter | `api/llm/router.py` | `Tier` enum (0 local Ollama, 1 free-tier Gemini, 2 paid Claude/OpenRouter), budget cap enforcement |
| VectorStore | `api/memory/vectorstore.py` | in-process embedding storage, no external service |
| FastAPI app | `api/main.py` (511 lines, 17 routes + `/ws`) | HTTP/WebSocket surface, admin guard, crisis rate limiting |
| City stage | `web/src/city/CityStage3D.tsx` | Three.js daylight town, people, cordons, hover, camera glide to `store.focus` |
| Narration rules | `web/src/city/narration.ts` (tested in `narration.test.ts`) | which events become a sentence, its wording, queue order; pure functions |
| Narrator | `web/src/city/Narrator.tsx` | timing, history browsing, sets `store.focus` |

## Failure modes

| Failure | Effect | Mitigation |
|---|---|---|
| Render free-tier cold start (~25s after 15 min idle) | first visitor of the day waits | GitHub Actions cron asks for a `/health` ping every 10 min, but GitHub throttles scheduled runs to gaps of hours, so this reduces cold starts rather than preventing them (a 23 s cold start was measured on 2026-10-28) |
| A visitor spams `POST /crisis` | burns the shared LLM budget / spams every viewer's WebSocket | 30s global cooldown + a per-UTC-day cap (`CRISIS_DAILY_CAP`), both enforced in `_check_crisis_budget()` |
| `POST /speed` or a manual crisis resolve from a random visitor | changes the simulation for every viewer | gated behind `X-Admin-Token` (`require_admin`), open only when `ADMIN_TOKEN` is unset (local dev) |
| Process restart | the running society, its causal graph, and all debates are lost | accepted for a demo; nothing is durable by design (no database) |
| Frontend and backend on different hosts disagree on URL shape | every REST call 404s while the WebSocket still works, so the page looks alive | `API_ROOT` in `web/src/config.ts` is the backend origin in production and `/api` only in dev, where Vite's proxy strips the prefix; this bug shipped from July to November 2026 because only `/health` and the page were checked |
| More than 8 events logged between two broadcasts (fast speed, a debate and chatter at once) | the narrator never sees the earlier ones | accepted: the snapshot carries the last 8 by design; the Details drawer reads the full timeline over REST |
| A debate's async task outlives the process shutting down (or a test's event loop) | a dangling-task warning at teardown | tests construct/tear down the `Engine` per-test; production has no such teardown path since the process runs continuously |
| Causal-graph BFS at scale | walking backward from a crisis gets slower as the graph grows across a long-running session | acceptable at the 10-citizen / one-session scale this ships at; the first thing to change past that scale (see below) |

## Tradeoffs

| Choice | Gain | Cost |
|---|---|---|
| In-process state over a database | far simpler to build and deploy for a demo | zero durability, no horizontal scaling |
| One narrated sentence over seven always-open panels | a first-time visitor knows where to look | detail is one click away in the drawer, not on screen |
| Additive over multiplicative fusion (benchmarked in `research/tcmf_paper/`) | causally relevant but semantically distant memories actually surface | two terms to balance with a lambda hyperparameter |
| In-process vector store over Chroma/pgvector | no extra service at this scale (a handful of citizens, bounded memory streams) | must move out of process before many concurrent societies |
| `DEMO_MODE` on the public deploy | the deploy stays free; crisis injection and debates stay fully live | no ambient loop, which needs the $0 Ollama tier that the cloud cannot reach |

## Scaling (what would change first)

1. Vector store out of process (a real Chroma/pgvector service) - the first bottleneck
   past a handful of citizens or a long-running session with many memories.
2. Simulation state out of the FastAPI process into its own worker, with the API layer
   talking to it over a queue or RPC - needed before more than one concurrent society
   could run, and before a restart could avoid losing state.
3. Causal graph as a real graph database (or at least persisted) once a session's graph
   outgrows a few hundred nodes or needs to survive a restart.
4. WebSocket fan-out via a pub/sub layer (Redis or similar) once viewer count grows
   past what one process's `ConnectionManager` should hold directly.

## Security

- Write endpoints (`/speed`, both `/resolve` routes) require `X-Admin-Token` when
  `ADMIN_TOKEN` is configured (the public deploy); open only on an unconfigured local
  instance.
- `POST /crisis` stays public (it is the point of the demo) but is cooldown- and
  daily-cap-limited so it cannot be used to run up the LLM budget.
- CORS origins are an explicit allow-list from settings, never `"*"`.
- No secrets in `render.yaml`; `OPENROUTER_API_KEY`, `ADMIN_TOKEN`, etc. are
  `sync: false` and set only in the Render dashboard.

## Observability

One structured (JSON) log line per LLM call, on its own `civos.llm.calls` logger so
it's greppable out of Render's raw log stream with no aggregator wired up:
`call_id`, `tier_requested`, `tier_used`, `downgraded`, `model`, `latency_ms`,
`cost_usd`, `input_tokens`/`output_tokens`, and `ok`/`error` - emitted whether the call
succeeds or raises, so a failed call is visible in the stream rather than showing up
only as a missing success line (`api/llm/router.py`, `LLMRouter._log_call`). This is
what lets the $0-in-dev / near-$0-in-prod claim be demonstrated from the logs, not just
read off the code. `SpendTracker.record()`'s existing human-readable line
(`Tier-2 call #N ... total=$X/cap`) stays alongside it for at-a-glance budget tracking.

## Cost

$0 in local development (Ollama only). On the public deploy, `PREMIUM_MODE=true` allows
Tier 2 (Claude/OpenRouter) for the council Synthesizer only; `TIER2_BUDGET_USD` caps
total spend per process lifetime (reset on every Render restart, so it is a
per-process-lifetime ceiling, not a true monthly one - documented in `CLAUDE.md`).

## Future

- Move the vector store and simulation state out of process (see Scaling).
- A durable session store so a demo society survives a Render restart, if that ever
  becomes worth the added infrastructure for what is currently a stateless-by-design
  demo.
