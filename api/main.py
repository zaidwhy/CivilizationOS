"""CivilizationOS FastAPI entrypoint.

A single shared simulation Engine is advanced by one background loop on startup;
every connected WebSocket client receives the same broadcast world snapshots, so
all viewers watch the same city. REST endpoints expose health, an LLM smoke test,
per-agent detail, and PANTHEON council controls.

Phase 5 additions:
  POST /speed           — change tick interval (0.1–5.0 seconds)
  POST /crisis/{key}/resolve — manually end an active crisis
  GET  /timeline        — causal event history for the Timeline panel

Run:  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings
from .llm import Tier, get_router
from .sim.engine import Engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civos.api")

settings = get_settings()
engine = Engine(seed=settings.sim_seed, use_llm=True)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def _sim_loop() -> None:
    """Single authoritative clock: advance the world and broadcast each tick."""
    while True:
        try:
            snap = await engine.advance()
            await manager.broadcast(snap)
        except Exception:
            logger.exception("sim loop tick failed")
        await asyncio.sleep(engine.tick_interval)


async def _broadcast_debate_turn(turn) -> None:
    await manager.broadcast({
        "type": "debate_turn",
        "debate_id": turn.debate_id,
        "institution_id": turn.institution_id,
        "role": turn.role,
        "name": turn.name,
        "text": turn.text,
        "tick": turn.tick,
        "is_final": turn.is_final,
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine._on_debate_turn = _broadcast_debate_turn
    task = asyncio.create_task(_sim_loop())
    logger.info("simulation started (seed=%s, use_llm=%s)", settings.sim_seed, engine.use_llm)
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="CivilizationOS", version="0.8.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- core ----

@app.get("/health")
async def health() -> dict:
    s = get_settings()
    router = get_router()
    return {
        "status": "ok",
        "version": "0.8.0",
        "premium_mode": s.premium_mode,
        "tick": engine.tick_count,
        "tick_interval": engine.tick_interval,
        "citizens": len(engine.citizens),
        "active_crises": [t.name for t, _ in engine._active_templates],
        "causal_events": len(engine.causal_graph),
        "brains": {
            "local": s.ollama_chat_model,
            "council": s.ollama_council_model if s.has_finetuned_council else None,
            "free": s.gemini_model if s.has_gemini else None,
            "premium": s.claude_member_model if s.has_claude else None,
        },
        "tier2_spent_usd": round(router.spend.spent_usd, 4),
        "tier2_budget_usd": s.tier2_budget_usd,
    }


@app.get("/agent/{agent_id}")
async def agent(agent_id: str) -> dict:
    detail = engine.agent_detail(agent_id)
    return detail or {"error": "not found", "id": agent_id}


@app.get("/llm/ping")
async def llm_ping(tier: int = 0) -> dict:
    router = get_router()
    result = await router.complete(
        prompt="Reply with a single short sentence confirming you are online.",
        system="You are a terse status probe.",
        tier=Tier(tier),
        max_tokens=64,
    )
    return {
        "text": result.text.strip(),
        "tier_requested": result.tier_requested.name,
        "tier_used": result.tier_used.name,
        "downgraded": result.downgraded,
        "model": result.model,
        "cost_usd": round(result.cost_usd, 6),
    }


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json(engine.snapshot())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("ws error")
        manager.disconnect(websocket)
        with contextlib.suppress(Exception):
            await websocket.close()


# ---- Phase 5: simulation controls ----

class SpeedRequest(BaseModel):
    seconds_per_tick: float = 1.0


@app.post("/speed")
async def set_speed(req: SpeedRequest) -> dict:
    """Adjust simulation speed. 0.1 = very fast, 5.0 = very slow."""
    clamped = max(0.1, min(5.0, req.seconds_per_tick))
    engine.tick_interval = clamped
    return {"tick_interval": engine.tick_interval}


@app.post("/crisis/{template_key}/resolve")
async def resolve_crisis(template_key: str) -> dict:
    """Manually resolve an active crisis by its template key."""
    from .sim.events import CRISIS_TEMPLATES
    if template_key not in CRISIS_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown crisis template '{template_key}'")
    result = engine.resolve_crisis(template_key)
    if result is None:
        raise HTTPException(status_code=409, detail=f"Crisis '{template_key}' is not currently active")
    return {"resolved": template_key, "message": result, "tick": engine.tick_count}


@app.post("/crisis/id/{crisis_id}/resolve")
async def resolve_crisis_by_id(crisis_id: str) -> dict:
    """Resolve any crisis by its registry ID — works for custom and template crises."""
    result = engine.resolve_crisis_by_id(crisis_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Crisis '{crisis_id}' not found or already resolved",
        )
    return {"resolved": crisis_id, "message": result, "tick": engine.tick_count}


@app.get("/timeline")
async def get_timeline(k: int = 60) -> dict:
    """Causal event history for the Timeline panel (newest first)."""
    events = engine.timeline(k=min(k, 200))
    return {"events": events, "total_nodes": len(engine.causal_graph)}


# ---- PANTHEON council endpoints ----

class CrisisRequest(BaseModel):
    text: str
    institution_id: str
    severity: float = 0.7
    template_key: str | None = None


@app.post("/crisis")
async def post_crisis(req: CrisisRequest) -> dict:
    from .agents.council import COUNCILS
    from .sim.events import CRISIS_TEMPLATES
    if req.institution_id not in COUNCILS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown institution '{req.institution_id}'. Valid: {list(COUNCILS.keys())}",
        )
    tmpl = CRISIS_TEMPLATES.get(req.template_key or "")
    text = req.text or (tmpl.description if tmpl else "")
    if not text:
        raise HTTPException(status_code=422, detail="crisis text is required")
    crisis = await engine.inject_crisis(
        text=text,
        institution_id=req.institution_id,
        severity=req.severity,
        template_key=req.template_key,
    )
    return {
        "crisis_id": crisis.id,
        "debate_id": crisis.debate_id or "(debate starting…)",
        "institution_id": crisis.institution_id,
        "tick": crisis.tick,
        "template": req.template_key,
    }


@app.get("/events/templates")
async def get_templates() -> dict:
    from .sim.events import CRISIS_TEMPLATES
    return {
        "templates": [
            {
                "key": t.key,
                "name": t.name,
                "description": t.description,
                "primary_institution": t.primary_institution,
                "secondary_institutions": t.secondary_institutions,
                "resolution_text": t.resolution_text,
            }
            for t in CRISIS_TEMPLATES.values()
        ]
    }


@app.get("/debates/{debate_id}")
async def get_debate(debate_id: str) -> dict:
    turns = engine.crises.get_debate(debate_id)
    return {
        "debate_id": debate_id,
        "turns": [
            {
                "role": t.role,
                "name": t.name,
                "text": t.text,
                "tick": t.tick,
                "is_final": t.is_final,
            }
            for t in turns
        ],
        "complete": any(t.is_final for t in turns),
    }


@app.get("/graph")
async def get_graph() -> dict:
    """Citizen social graph: nodes with fear levels + weighted affinity edges."""
    nodes = [
        {
            "id": c.p.id,
            "name": c.p.name,
            "occupation": c.p.occupation,
            "fear": round(c.fear, 2),
        }
        for c in engine.citizens.values()
    ]
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for c in engine.citizens.values():
        for other_id, affinity in c.relationships.items():
            if other_id not in engine.citizens:
                continue
            key = (min(c.p.id, other_id), max(c.p.id, other_id))
            if key not in seen and abs(affinity) > 0.05:
                seen.add(key)
                edges.append({
                    "source": c.p.id,
                    "target": other_id,
                    "weight": round(affinity, 2),
                    "positive": affinity >= 0,
                })
    return {"nodes": nodes, "edges": edges}


@app.get("/stats")
async def get_stats() -> dict:
    """Simulation statistics for the StatsPanel: fear histogram, memory counts, debate count."""
    fears = [c.fear for c in engine.citizens.values()]
    buckets = [0, 0, 0, 0, 0]  # 0-20%, 20-40%, 40-60%, 60-80%, 80-100%
    for f in fears:
        buckets[min(4, int(f * 5))] += 1
    return {
        "tick": engine.tick_count,
        "avg_fear": round(sum(fears) / len(fears), 3) if fears else 0,
        "fear_buckets": buckets,
        "memory_counts": {c.p.name: len(c.memory) for c in engine.citizens.values()},
        "total_debates": len(engine.crises.all_debates()),
        "active_crises": len(engine._active_templates),
        "causal_events": len(engine.causal_graph),
    }


@app.get("/crises")
async def get_crises() -> dict:
    return {
        "crises": [
            {
                "id": c.id,
                "text": c.text,
                "tick": c.tick,
                "institution_id": c.institution_id,
                "debate_id": c.debate_id,
                "severity": c.severity,
                "template_key": c.template_key,
                "resolved": c.resolved,
            }
            for c in engine.crises.list_crises()
        ]
    }
