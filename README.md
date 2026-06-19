# CivilizationOS

> A multi-agent society simulation powered by autonomous AI citizens, institutional councils, and a novel RAG architecture — built as a portfolio-grade AI project on a near-zero budget.

---

## What It Is

CivilizationOS is a **hybrid of two paradigms**:

| Layer | What it is |
|---|---|
| **AGORA** | ~10 autonomous citizen-agents *live* in an animated isometric city. They follow daily routines, have conversations, build relationships, and form episodic memories. |
| **PANTHEON** | 5 societal institutions (Government, Economy, Healthcare, Media, Police) are each governed by a **council of 5 AI specialists** that debate before acting. |

You inject crises — **Pandemic, Drought, Cyberattack, Election, Crime Wave** — and watch society react in real time. Councils deliberate, citizens respond with occupation-specific fear, relationships shift, and the city's causal history builds up in a graph.

---

## Key Technical Differentiators

### 1. Temporal-Causal Memory Fusion (TCMF) — the novel RAG

Standard RAG retrieves by semantic similarity. TCMF fuses **two retrieval streams**:

```
AGORA stream   — per-citizen episodic memories scored by:
                   relevance (embedding cosine) × recency (exp-decay) × importance (LLM-rated)

PANTHEON stream — society-wide causal graph (NetworkX DiGraph):
                   crisis → council decision → policy outcome → downstream event

Fused score = episodic_score(m, q) × (1 + λ × causal_boost(m))
```

The `causal_boost` rewards memories that are semantically near the **causal ancestors** of the current crisis. A witness at the scene of a root cause outranks someone who heard about it second-hand. No off-the-shelf RAG system does this.

### 2. 3-Tier LLM Router — runs at $0 in dev

| Tier | Brain | Used for | Cost |
|---|---|---|---|
| **0** | Ollama + Qwen2.5 3B (local) | Citizen conversations, observations, reflections, embeddings | $0 |
| **1** | Gemini Flash (free tier) | Council Historian / Strategist / Skeptic / Predictor | $0 |
| **2** | Claude API (Haiku/Sonnet) | Council Synthesizer (VERDICT turn) in premium mode | ~$0.002 / debate |

`PREMIUM_MODE=false` in `.env` → everything runs locally at $0. Flip to `true` for the demo.

### 3. Council Debate Architecture

Each institution runs a structured 5-role debate when a crisis is injected:

```
📜 Historian  — surfaces causal precedents from TCMF context
⚔️ Strategist — proposes 2 specific actionable interventions
🔍 Skeptic    — challenges the Strategist; names hidden risks + safeguards
🔮 Predictor  — probability estimate of success + worst-case scenario
⚖️ Synthesizer— VERDICT: who does what, measured by what success metric
```

**Institution lens** shapes every debate: Government debates through law + democratic legitimacy; Economy through markets + trade; Healthcare through clinical protocols; Media through information integrity; Police through proportionality + civil rights.

### 4. Occupation-Specific Crisis Reactions

Each citizen reacts through the lens of their profession:
- **Doctor** on pandemic: *"As a doctor I need to prepare triage protocols immediately — we'll be overwhelmed."*
- **Journalist** on election: *"Three sources have contacted me about voting irregularities in the same district."*
- **Trader** on drought: *"Food futures are spiking and the exchange algorithms are amplifying the panic."*

### 5. Causal Graph — crisis → debate → verdict → downstream

Every injected crisis, council decision, and resolution is a node in a NetworkX directed graph with temporal causal edges. Council verdicts link back to their originating crisis. The **Timeline panel** visualises this live.

---

## Architecture

```
civilizationos/
├── api/                       Python 3.12 + FastAPI backend
│   ├── main.py                FastAPI app, WebSocket hub, all REST endpoints
│   ├── config.py              Settings (PREMIUM_MODE, API keys, tick speed)
│   ├── sim/
│   │   ├── engine.py          Async tick loop, city state, crisis injection
│   │   ├── world.py           Grid, locations, day-phase clock
│   │   ├── crisis.py          CrisisRegistry — debate transcripts, state
│   │   └── events.py          5 crisis templates with occupation-specific effects
│   ├── agents/
│   │   ├── citizen.py         Autonomous citizen (movement, memory, fear, backstory)
│   │   ├── council.py         5-specialist PANTHEON council with institution lenses
│   │   └── personas.py        10 seed citizens with rich backstory + traits
│   ├── memory/
│   │   ├── stream.py          Episodic memory stream (relevance×recency×importance)
│   │   ├── causal_graph.py    NetworkX temporal causal graph (crisis→decision chain)
│   │   ├── tcmf.py            Temporal-Causal Memory Fusion retriever
│   │   └── vectorstore.py     In-memory embedding store
│   └── llm/
│       └── router.py          3-tier router: Ollama → Gemini → Claude
│
├── web/                       React + Vite + TypeScript frontend
│   └── src/
│       ├── App.tsx            Layout, speed slider, dynamic spend counter
│       ├── city/
│       │   ├── CityStage.tsx  PixiJS isometric city (citizens, buildings, crisis effects)
│       │   └── iso.ts         Isometric math, palettes, crisis building colours
│       ├── panels/
│       │   ├── Inspector.tsx        Citizen mind viewer (memory, relationships, backstory, fear)
│       │   ├── CouncilChamber.tsx   Debate UI (live turns, animated deliberation, resolve, history)
│       │   ├── EventFeed.tsx        City event log
│       │   ├── RelationshipGraph.tsx Social graph canvas
│       │   └── Timeline.tsx         Causal event timeline (crisis → decision chain)
│       ├── components/
│       │   └── Onboarding.tsx       5-step first-run walkthrough
│       └── ws/
│           └── store.ts             Zustand store + WebSocket client + health poll
│
└── ml/                        Fine-tuning + MLOps (Phase 4)
    ├── train_lora.ipynb        Unsloth LoRA on Qwen2.5 3B → GGUF → Ollama
    ├── dataset/                Synthetic council-voice dataset generator
    ├── evals/                  Persona-consistency + debate-quality eval harness
    └── mlflow/                 Local MLflow tracking store
```

---

## Quick Start

### Prerequisites
- Python 3.11+, Node 18+
- [Ollama](https://ollama.com) running as a background service
- Models pulled: `ollama pull qwen2.5:3b-instruct && ollama pull nomic-embed-text`

### Setup

```bash
# Python environment
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r api/requirements.txt

# Frontend
cd web && npm install && cd ..

# Environment (optional — free mode runs without any keys)
copy .env.example .env
# Add GEMINI_API_KEY for Tier-1
# Add ANTHROPIC_API_KEY + PREMIUM_MODE=true for Tier-2 (Claude council verdicts)
```

### Run (two terminals, both in the project root)

**Terminal 1 — Backend:**
```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python -m uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd web; npm run dev
```

Open **http://localhost:5173** in your browser.

### Run tests
```bash
.venv/Scripts/python -m pytest api/tests/ -v
# 48 tests, all pass
```

---

## Demo Walkthrough

1. Wait a few ticks for citizens to start moving and talking.
2. Click any citizen dot → **Inspector panel** shows their mind, memories, and backstory.
3. Scroll the right sidebar to **⚖ PANTHEON COUNCIL**.
4. Click **🦠 Pandemic Outbreak** preset → click **⚡ Inject Crisis**.
5. Watch the 5-specialist debate stream live. The Synthesizer issues a VERDICT.
6. Observe:
   - Citizens' dots turn red (fear).
   - The Clinic building dims and shows ⛔ (closed).
   - The city feed fills with crisis events and debate excerpts.
   - The **Timeline panel** (bottom of sidebar) shows the causal chain.
7. Click **✓ resolve** badge to end the crisis.
8. Use the **speed slider** in the header to fast-forward time.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status, spend counter, tick interval |
| GET | `/agent/{id}` | Citizen detail: memories, relationships, backstory |
| POST | `/crisis` | Inject a crisis (triggers council debate) |
| POST | `/crisis/{key}/resolve` | Manually resolve an active crisis |
| GET | `/crises` | All injected crises |
| GET | `/debates/{id}` | Full debate transcript |
| GET | `/events/templates` | All crisis presets |
| GET | `/timeline` | Causal event history (newest first) |
| POST | `/speed` | Set tick interval (0.1–5.0 seconds) |
| GET | `/llm/ping?tier=0` | Smoke-test a specific LLM tier |
| WS  | `/ws` | Live world snapshots + debate turns |

---

## Phases Completed

| Phase | What was built | Status |
|---|---|---|
| 0 | 3-tier LLM router, FastAPI + WebSocket, React scaffold | ✅ |
| 1 | 10 autonomous citizens, episodic memory, PixiJS isometric city | ✅ |
| 2 | PANTHEON councils, TCMF RAG, CouncilChamber UI | ✅ |
| 3 | 5 crisis templates, cross-institution effects, RelationshipGraph, EventFeed | ✅ |
| 4 | LoRA fine-tune notebook (Colab), MLflow tracking, eval harness | ✅ |
| 5 | Backstory personas, institution-specific debate lenses, verdict→causal graph, speed control, crisis resolution, Timeline panel, Onboarding tour, crisis building visuals, dynamic spend counter | ✅ |

---

## Cost Breakdown

| Component | Cost |
|---|---|
| All citizen AI (conversations, reflections, embeddings) | $0 (Ollama local) |
| Council Historian / Strategist / Skeptic / Predictor | $0 (Gemini free tier) |
| Council Synthesizer — PREMIUM_MODE=true only | ~$0.002 / debate |
| Full demo (5 crises × all councils) | ~$0.05–0.30 |
| LoRA fine-tuning (Colab T4) | $0 |
| Hosting (Vercel frontend) | $0 |
| **Total project spend** | **< $5** |

---

## Four Required Pillars

| Pillar | CivilizationOS delivery |
|---|---|
| Multi-agent system | 10 citizen-agents + 5 × 5-specialist councils = 35 agents total |
| RAG (novel retrieval) | Temporal-Causal Memory Fusion — episodic memory × societal causal graph |
| Fine-tuned model + MLOps | LoRA fine-tune on Qwen2.5 3B, MLflow tracking, persona-consistency evals |
| Full-stack + Claude API | React + PixiJS ↔ FastAPI/WebSocket; Claude powers the Synthesizer turn |
