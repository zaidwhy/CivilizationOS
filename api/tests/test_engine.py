"""Tests for the simulation engine in deterministic (rule-based) mode."""
from __future__ import annotations

import pytest

from api.sim.engine import Engine
from api.sim.world import phase_for_tick, DayPhase


async def run_ticks(engine: Engine, n: int) -> dict:
    snap = engine.snapshot()
    for _ in range(n):
        snap = await engine.advance()
    return snap


@pytest.mark.asyncio
async def test_determinism_same_seed_same_positions():
    a = Engine(seed=7, use_llm=False)
    b = Engine(seed=7, use_llm=False)
    sa = await run_ticks(a, 80)
    sb = await run_ticks(b, 80)
    pos_a = [(c["id"], c["x"], c["y"]) for c in sa["citizens"]]
    pos_b = [(c["id"], c["x"], c["y"]) for c in sb["citizens"]]
    assert pos_a == pos_b


@pytest.mark.asyncio
async def test_citizens_reach_workplace_during_work_phase():
    e = Engine(seed=1, use_llm=False)
    await run_ticks(e, 130)              # well into the WORK phase
    assert phase_for_tick(130) == DayPhase.WORK
    ava = e.citizens["ava"]
    assert ava.location_id == ava.p.workplace_id


@pytest.mark.asyncio
async def test_conversations_happen_and_form_memories():
    e = Engine(seed=3, use_llm=False)
    await run_ticks(e, 150)
    convo_events = [ev for ev in e.event_log if ev["kind"] == "conversation"]
    assert convo_events, "expected at least one conversation in a populated commons"
    # the citizens involved should carry conversation memories
    total_convo_mem = sum(
        1
        for c in e.citizens.values()
        for m in c.memory.memories.values()
        if m.kind == "conversation"
    )
    assert total_convo_mem > 0


@pytest.mark.asyncio
async def test_snapshot_shape():
    e = Engine(seed=1, use_llm=False)
    snap = await run_ticks(e, 5)
    assert snap["type"] == "world"
    assert len(snap["citizens"]) == 10
    assert {"w", "h"} <= snap["grid"].keys()
    assert all({"id", "x", "y", "action"} <= c.keys() for c in snap["citizens"])


@pytest.mark.asyncio
async def test_agent_detail_returns_memories():
    e = Engine(seed=1, use_llm=False)
    await run_ticks(e, 130)
    detail = e.agent_detail("finn")
    assert detail is not None
    assert detail["name"] == "Finn Doyle"
    assert isinstance(detail["memories"], list)
    assert e.agent_detail("nobody") is None
