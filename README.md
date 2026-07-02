# CivilizationOS

> A multi-agent society simulation powered by autonomous AI citizens, institutional councils, and a novel RAG architecture - built as a portfolio-grade AI project on a near-zero budget.

**Status: feature-complete (Phases 0-13).** 61 backend tests passing, 0 TypeScript errors.

![CivilizationOS - 3D city with live citizen agents](docs/screenshots/city.png)

---

## What It Is

CivilizationOS is a **hybrid of two paradigms**:

| Layer | What it is |
|---|---|
| **AGORA** | 10 autonomous citizen-agents *live* in an animated 3D city. They follow daily routines, have conversations, build relationships, form factions, and accumulate episodic memories. |
| **PANTHEON** | 5 societal institutions (Government, Economy, Healthcare, Media, Police) are each governed by a **council of 5 AI specialists** that debate before acting. |

You inject crises — Pandemic, Drought, Cyberattack, Election, Crime Wave, and more — and watch society react in real time. Councils deliberate, citizens respond with occupation-specific fear, relationships shift into alliances and rivalries, and the city's causal history builds up in a queryable graph.

---

## Key Technical Differentiators

### 1. Temporal-Causal Memory Fusion (TCMF) — the novel RAG

Standard RAG retrieves by semantic similarity. TCMF fuses **two retrieval streams**:

```
AGORA stream    — per-citizen episodic memories scored by:
                    relevance (embedding cosine) × recency (exp-decay) × importance (LLM-rated)

PANTHEON stream — society-wide causal graph (NetworkX DiGraph):
                    crisis → council decision → policy outcome → downstream event

Fused score = episodic_score(m, q) × (1 + λ × causal_boost(m))
```

The `causal_boost` rewards memories that are semantically near the **causal ancestors** of the current crisis. A witness at the scene of a root cause outranks someone who heard about it second-hand. No off-the-shelf RAG system does this.

**Full design write-up: [docs/tcmf.md](./docs/tcmf.md)** - the scoring formulas with code, a worked plague-outbreak example, the honest tradeoffs (inferred causality is noisy, three tunable parameters, BFS latency at scale), and what v2 would change.

### 2. 3-Tier LLM Router — runs at $0 in dev

| Tier | Brain | Used for | Cost |
|---|---|---|---|
| **0** | Ollama + Qwen2.5 3B (local) | Citizen conversations, observations, reflections, embeddings | $0 |
| **1** | Gemini Flash (free tier) | Council Historian / Strategist / Skeptic / Predictor | $0 |
| **2** | Claude API (Haiku/Sonnet) | Council Synthesizer (VERDICT turn) in premium mode | ~$0.002 / debate |

`PREMIUM_MODE=false` in `.env` → everything runs locally at $0. Flip to `true` for the demo. A LoRA fine-tune of Qwen2.5 3B (`civos-council`) can also take over the 4 non-verdict debate roles once exported from the training notebook — see [Fine-Tuned Council Model](#fine-tuned-council-model).

### 3. Council Debate Architecture

Each institution runs a structured 5-role debate when a crisis is injected:

```
📜 Historian   — surfaces causal precedents from TCMF context
⚔️ Strategist  — proposes 2 specific actionable interventions
🔍 Skeptic     — challenges the Strategist; names hidden risks + safeguards
🔮 Predictor   — probability estimate of success + worst-case scenario
⚖️ Synthesizer — VERDICT: who does what, measured by what success metric
```

**Institution lens** shapes every debate: Government debates through law + democratic legitimacy; Economy through markets + trade; Healthcare through clinical protocols; Media through information integrity; Police through proportionality + civil rights. Councils also see **active citizen factions** in their context, so verdicts account for real social alliances.

### 4. Emergent Crisis Injection

Crises don't only arrive by hand. If average citizen fear stays above a sustained threshold for long enough, the engine synthesises a new crisis via LLM and injects it automatically — with a compound-cascade path for genuine emergencies and a cooldown to prevent spam. A `TENSION` meter in the header shows the countdown before an emergent crisis fires.

### 5. Citizen Factions

Union-find over mutual relationship affinity (>0.60, both directions) detects social blocs in real time — trade guilds, press circles, justice fronts. Factions get named, colour-ringed in the relationship graph, badged in the citizen inspector, and injected into every council's debate context.

### 6. Council Track Record

Each institution's verdicts are scored: fear measured 60 ticks after a verdict is delivered, compared to fear before, and converted into an effectiveness percentage (50 = neutral). Over a session you can see which councils actually make things better.

### 7. Occupation-Specific Crisis Reactions

Each citizen reacts through the lens of their profession — 42 distinct first-person reactions across 10 occupations × 5 crisis types:
- **Doctor** on pandemic: *"As a doctor I need to prepare triage protocols immediately — we'll be overwhelmed."*
- **Journalist** on election: *"Three sources have contacted me about voting irregularities in the same district."*
- **Trader** on drought: *"Food futures are spiking and the exchange algorithms are amplifying the panic."*

### 8. Causal Graph + Story Rewind

Every injected crisis, council decision, and resolution is a node in a NetworkX directed graph with temporal causal edges. The **Story Rewind** panel lets you scrub a slider back through the tick history and watch the causal chain unfold, or expand any event for its full text.

---

## Architecture

```
civilizationos/
├── api/                       Python 3.12 + FastAPI backend
│   ├── main.py                 FastAPI app, WebSocket hub, all REST endpoints (v0.13.0)
│   ├── config.py                Settings (PREMIUM_MODE, API keys, tick speed)
│   ├── sim/
│   │   ├── engine.py            Async tick loop, crisis injection, verdict effects,
│   │   │                        emergent crises, council track record, factions
│   │   ├── world.py             20×15 grid, 10 named locations, day-phase clock
│   │   ├── crisis.py            CrisisRegistry — debate transcripts, resolved/emergent flags
│   │   └── events.py            Crisis templates with occupation-specific effects
│   ├── agents/
│   │   ├── citizen.py           Autonomous citizen (movement, memory, fear, backstory)
│   │   ├── council.py           5-specialist PANTHEON council with institution lenses
│   │   └── personas.py          10 seed citizens with rich backstory + traits
│   ├── memory/
│   │   ├── stream.py            Episodic memory stream (relevance × recency × importance)
│   │   ├── causal_graph.py      NetworkX temporal causal graph (crisis → decision chain)
│   │   ├── tcmf.py               Temporal-Causal Memory Fusion retriever
│   │   └── vectorstore.py       In-process embedding store (no external DB)
│   └── llm/
│       └── router.py            3-tier router: Ollama → Gemini → Claude
│
├── web/                        React 18 + Vite + TypeScript frontend
│   └── src/
│       ├── App.tsx              Layout, speed slider, spend counter, tension meter
│       ├── city/
│       │   ├── CityStage3D.tsx  Three.js 3D city — orbit camera, bloom, PCF shadows (primary)
│       │   ├── CityStage.tsx    PixiJS isometric city (kept as fallback)
│       │   └── iso.ts           Isometric math, palettes
│       ├── panels/
│       │   ├── Inspector.tsx         Citizen mind viewer (memory, relationships, backstory, fear sparkline)
│       │   ├── CouncilChamber.tsx    Live debate UI, institution-coloured debate archive
│       │   ├── EventFeed.tsx         City event log
│       │   ├── RelationshipGraph.tsx Force-directed affinity graph with faction rings
│       │   ├── Timeline.tsx          Story Rewind — scrubbable causal event spine
│       │   ├── StatsPanel.tsx        Fear histogram, council scorecards, session export
│       │   └── Chronicle.tsx         LLM-generated newspaper-style city dispatch
│       ├── components/
│       │   └── Onboarding.tsx        5-step dismissible first-run tour
│       └── ws/
│           └── store.ts               Zustand store + WebSocket client + health poll
│
└── ml/                         Fine-tuning + MLOps
    ├── train_lora.ipynb         Unsloth LoRA fine-tune on Qwen2.5 3B → GGUF → Ollama
    ├── dataset/                 Synthetic council-voice dataset generator
    ├── evals/                   Persona-consistency + debate-quality eval harness
    └── mlflow/                  Local MLflow tracking store
```

---

## Quick Start

### Prerequisites
- Python 3.12, Node 18+
- [Ollama](https://ollama.com) running as a background service
- Models pulled: `ollama pull qwen2.5:3b-instruct && ollama pull nomic-embed-text`

### Setup

```bash
# Python environment
python -m venv .venv312
.venv312\Scripts\activate          # Windows PowerShell
pip install -r api/requirements.txt

# Frontend
cd web && npm install && cd ..

# Environment (optional — free mode runs without any keys)
# Create a .env file in the project root:
#   GEMINI_API_KEY=...            (optional, Tier 1)
#   ANTHROPIC_API_KEY=...         (optional, Tier 2)
#   PREMIUM_MODE=false            (set true for Claude council verdicts)
#   OLLAMA_COUNCIL_MODEL=...      (optional, fine-tuned model name once exported)
```

### Run (two terminals, both in the project root)

**Terminal 1 — Backend:**
```powershell
$env:PYTHONIOENCODING="utf-8"
.venv312\Scripts\python -m uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd web; npm run dev
```

Open **http://localhost:5173** in your browser.

### Run tests
```bash
.venv312\Scripts\python -m pytest api/tests/ -q
# 61 tests, all pass
```

---

## Demo Walkthrough

![Citizen Inspector - memories, relationships, fear history](docs/screenshots/inspector.png)

1. Wait a few ticks for citizens to start moving and talking.
2. Click any citizen → **Inspector panel** shows their mind, memories, backstory, and fear history.
3. Scroll the right sidebar to **⚖ PANTHEON COUNCIL**.
4. Click **🦠 Pandemic Outbreak** preset (or use the **Scenario Launcher**) → inject the crisis.
5. Watch the 5-specialist debate stream live. The Synthesizer issues a VERDICT.
6. Observe:
   - Citizens glow red with fear; buildings dim and show a crisis pulse when closed.
   - The city feed and **Chronicle** dispatch narrate what's happening.
   - The **Story Rewind** panel builds a scrubbable causal chain.
   - Factions may form or fracture as relationships shift under pressure.
7. Click **✓ resolve** on a crisis badge to end it, or let a verdict partially reopen locations.
8. Use the speed slider to fast-forward time; watch the **TENSION** meter if you leave fear to rise on its own — an emergent crisis may fire without you touching anything.

---

## Fine-Tuned Council Model

`ml/train_lora.ipynb` fine-tunes Qwen2.5 3B on a synthetic council-voice dataset (Unsloth QLoRA, free Colab T4) and exports a GGUF. The routing code in `api/agents/council.py` is already wired to use it for the four non-verdict debate roles (Synthesizer stays on Claude/Gemini — binding verdicts benefit from the stronger model).

To activate:
```bash
ollama create civos-council -f ml/Modelfile
```
Then set `OLLAMA_COUNCIL_MODEL=civos-council` in `.env` and restart the API. A purple 🧠 pill appears in the header once active.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status, version, spend counter, tick interval, active brains |
| GET | `/agent/{id}` | Citizen detail: memories, relationships, backstory |
| WS  | `/ws` | Live world snapshots + debate turn stream |
| GET | `/llm/ping?tier=0` | Smoke-test a specific LLM tier |
| POST | `/crisis` | Inject a crisis (triggers council debate) |
| GET | `/crises` | All registry crises (template key, resolved, emergent flags) |
| GET | `/debates/{id}` | Full debate transcript |
| GET | `/events/templates` | All crisis presets |
| GET | `/timeline?k=60` | Causal event history, newest-first |
| POST | `/speed` | Set tick interval (0.1–5.0 seconds) |
| POST | `/crisis/{key}/resolve` | Resolve an active crisis by template key |
| POST | `/crisis/id/{id}/resolve` | Resolve any crisis (including custom ones) by registry ID |
| GET | `/graph` | Social graph: nodes + weighted affinity edges |
| GET | `/stats` | Fear histogram, memory counts, session counters |
| GET | `/track_record` | Per-council debates, verdicts, effectiveness score |
| GET | `/chronicle` | LLM-generated newspaper-style city dispatch (cached ~75s) |
| GET | `/export` | Full session JSON snapshot (citizens, events, crises, causal graph) |

---

## Cost Breakdown

| Component | Cost |
|---|---|
| All citizen AI (conversations, reflections, embeddings) | $0 (Ollama local) |
| Council Historian / Strategist / Skeptic / Predictor | $0 (Gemini free tier, or fine-tuned local model) |
| Council Synthesizer — `PREMIUM_MODE=true` only | ~$0.002 / debate |
| Full demo (multiple crises across all 5 councils) | ~$0.05–0.30 |
| LoRA fine-tuning (Colab T4) | $0 |
| **Total project spend** | **< $5** |

---

## Four Required Pillars

| Pillar | CivilizationOS delivery |
|---|---|
| Multi-agent system + domain problem | 10 citizen-agents + 5 institutional councils × 5 specialists = 35 agents governing a simulated society |
| RAG (novel retrieval) | Temporal-Causal Memory Fusion — episodic memory streams fused with a society-wide causal event graph |
| Fine-tuned model + MLOps | LoRA fine-tune on Qwen2.5 3B (Unsloth, free Colab T4), MLflow run tracking, persona-consistency + debate-quality eval harness |
| Full-stack + Claude API | React + Three.js 3D city ↔ FastAPI/WebSocket backend; Claude powers the council Synthesizer verdict in premium mode |

---

## Project History

Full phase-by-phase build record (0 through 13), design decisions, and plan-vs-reality notes live in [`MASTER_BUILD_LOG.md`](MASTER_BUILD_LOG.md).

**Deliberately out of scope for this build:**
- **Vercel deployment** — the frontend is deploy-ready (`cd web && vercel`), but the backend depends on a local Ollama instance, so a public deploy needs either a tunnel or a self-hosted API. Deferred by explicit choice, not left unfinished.
- **Demo video recording** — no recording tooling in-repo.
