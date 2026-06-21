# CivilizationOS — Master Build Log

Cumulative record of every phase, what shipped, and current status.

---

## Phase 9 — LoRA Fine-Tune + civos-council Model
**Date:** 2026-06-22 | **Handoff:** `HANDOFF_PHASE9.md`

### Shipped
- Fixed all Colab training errors (MLflow backend, SFTConfig migration, persona gate)
- Trained Qwen2.5-3B-Instruct LoRA on 300 council-voice samples (4 epochs, T4 GPU)
- Exported Q4_K_M GGUF (1.84 GB) via Unsloth + llama.cpp
- Registered `civos-council` in Ollama locally
- API confirmed: all 4 debate roles route to local fine-tuned model, $0 cost

### Current State
- `brains.council = "civos-council"` ✅
- `tier2_spent_usd = 0.00` at rest ✅
- Frontend purple pill renders ✅
- Tests: blocked by numpy/Python 3.14 incompatibility (pre-existing, unrelated to Phase 9)

---

## Phase 8 — Speech Bubbles, Graph Tooltip, Council Wiring
**Date:** 2026-06-21 | **Handoff:** `HANDOFF_PHASE8.md`

### Shipped
- Speech bubbles: name prefix stripped, 50-char cap, pointer tail, 10-tick TTL
- RelationshipGraph hover tooltip: name/occupation/fear/top-3-bonds, left-flip logic
- `council.py` routing bug fixed: `OLLAMA_COUNCIL_MODEL` now actually used (was always `None` before)
- `/health` exposes `brains` object with all 4 model slots
- Frontend `SpendCounter` shows purple 🧠 pill when fine-tuned council active
- 54 tests passing

---

## Phase 7 — Housing Crisis + Relationship Graph
**Date:** ~2026-06-20 | **Handoff:** `HANDOFF_PHASE7.md`

### Shipped
- 6th crisis template: Housing Crisis (`inst_economy`, closes Exchange)
- Occupation-specific observations for housing crisis (all 10 occupations)
- Force-directed Relationship Graph panel (D3, citizen nodes, affinity edges, click-select)
- `GET /graph` endpoint

---

## Phase 6 — Crisis System, Fear, Location Closure
**Date:** ~2026-06-19 | **Handoff:** `HANDOFF_PHASE6.md`

### Shipped
- 5 crisis templates: Pandemic, Drought, Cyberattack, Election, Crime Wave
- Fear system: `apply_fear()`, `decay_fear()`, fear-based routing to home
- Location closure: workplaces/commons close during crises, citizens reroute
- VERDICT reopens locations early
- `resolve_crisis_by_id()` for custom crises
- CouncilChamber: custom crisis resolve buttons, crisis badge list

---

## Phase 5 — PANTHEON Council + Debate System
**Date:** ~2026-06-18 | **Handoff:** `HANDOFF_PHASE5.md`

### Shipped
- 5-role council: Historian, Strategist, Skeptic, Predictor, Synthesizer
- Async debate pipeline with WebSocket streaming
- `POST /crisis` endpoint
- CouncilChamber panel with template presets and live transcript
- 3-tier LLM router: Tier0=Ollama, Tier1=Gemini, Tier2=Claude
- Spend tracking + `PREMIUM_MODE` flag

---

## Phase 4 — Memory, Reflection, Relationships
**Date:** ~2026-06-17

### Shipped
- MemoryStream with importance scoring and retrieval
- Reflection synthesis (Tier-1 call every 10 memories)
- Citizen-to-citizen relationship graph (affinity ±1.0)
- Relationship decay over time

---

## Phase 3 — Simulation Engine + World
**Date:** ~2026-06-16

### Shipped
- Engine tick loop with deterministic seeding
- 10 seed citizens with occupations, home/work locations
- Day phase system (Night/Work/Social)
- WebSocket broadcast of world snapshots
- `GET /agent/{id}` detail endpoint

---

## Phase 2 — Frontend Foundation
**Date:** ~2026-06-15

### Shipped
- React + Vite frontend with PixiJS city rendering
- WebSocket store (Zustand)
- CityStage canvas with citizen sprites
- StatsPanel, Timeline panel skeletons

---

## Phase 1 — Project Bootstrap
**Date:** ~2026-06-14

### Shipped
- FastAPI skeleton with `/health`, `/ws`
- Project structure: `api/`, `web/`, `ml/`
- `.env.example`, `requirements.txt`, `pyproject.toml`

---

## Backlog (open items as of Phase 9)

| Priority | Item | Notes |
|---|---|---|
| High | CouncilChamber: collapse old debates | UX debt — debates pile up |
| High | Demo recording | 2-min walkthrough video |
| Medium | 7th crisis template | `power_outage` or `flood` |
| Medium | Vercel deploy | Frontend deploys instantly; backend needs ngrok or Fly.io |
| Low | Rewind scrubber | Causal graph exists, no UI timeline scrubbing yet |
| Low | Expand training dataset | 300 → 1000 samples for better persona fidelity |
| Info | Tests need Python 3.11/3.12 | NumPy incompatible with Python 3.14 in current venv |
