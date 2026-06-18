"""CivilizationOS FastAPI entrypoint.

Phase 0: exposes health, an LLM router status endpoint, and a WebSocket that
streams a heartbeat tick. Phase 1 replaces the heartbeat with real world state
from the simulation engine.

Run:  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .llm import Tier, get_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civos.api")

app = FastAPI(title="CivilizationOS", version="0.0.1")
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
        "brains": {
            "local": s.ollama_chat_model,
            "free": s.gemini_model if s.has_gemini else None,
            "premium": s.claude_member_model if s.has_claude else None,
        },
        "tier2_spent_usd": round(router.spend.spent_usd, 4),
        "tier2_budget_usd": s.tier2_budget_usd,
    }


@app.get("/llm/ping")
async def llm_ping(tier: int = 0) -> dict:
    """Smoke-test the router at a requested tier (downgrades as configured)."""
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
    """Phase-0 heartbeat. Phase 1 streams real world snapshots over this channel."""
    await websocket.accept()
    s = get_settings()
    tick = 0
    try:
        while True:
            tick += 1
            await websocket.send_json({
                "type": "tick",
                "tick": tick,
                "premium_mode": s.premium_mode,
            })
            await asyncio.sleep(s.tick_seconds)
    except WebSocketDisconnect:
        logger.info("client disconnected after %d ticks", tick)
    except Exception:  # pragma: no cover - defensive
        logger.exception("ws loop error")
        with contextlib.suppress(Exception):
            await websocket.close()
