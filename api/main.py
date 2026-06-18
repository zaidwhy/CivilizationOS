"""CivilizationOS FastAPI entrypoint.

A single shared simulation Engine is advanced by one background loop on startup;
every connected WebSocket client receives the same broadcast world snapshots, so
all viewers watch the same city. REST endpoints expose health, an LLM smoke test,
and per-agent detail (memories + relationships) for the inspector panel.

Run:  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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
    """The single authoritative clock: advance the world and broadcast each tick."""
    while True:
        try:
            snap = await engine.advance()
            await manager.broadcast(snap)
        except Exception:
            logger.exception("sim loop tick failed")
        await asyncio.sleep(settings.tick_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_sim_loop())
    logger.info("simulation started (seed=%s, use_llm=%s)", settings.sim_seed, engine.use_llm)
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="CivilizationOS", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    router = get_router()
    return {
        "status": "ok",
        "premium_mode": s.premium_mode,
        "tick": engine.tick_count,
        "citizens": len(engine.citizens),
        "brains": {
            "local": s.ollama_chat_model,
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
        await websocket.send_json(engine.snapshot())  # immediate paint
        while True:
            await websocket.receive_text()  # client keepalive / future commands
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("ws error")
        manager.disconnect(websocket)
        with contextlib.suppress(Exception):
            await websocket.close()
