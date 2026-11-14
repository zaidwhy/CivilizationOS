"""The memories the TCMF causal boost is meant to reach must carry embeddings.

`_causal_boost_for_memory` returns 0 for a memory with no embedding, and compares it with
event embeddings. Crisis observations and verdict memories were written with none, and with
use_llm=False nothing at all was embedded (audit REPORT.md, "Found by reading the engine").
"""
from __future__ import annotations

import zlib
from dataclasses import replace

import numpy as np
import pytest

from api.agents.council import DebateTurn
from api.agents.personas import SEED_CITIZENS
from api.sim import engine as engine_mod
from api.sim.engine import Engine
from api.sim.events import CRISIS_TEMPLATES


class FakeRouter:
    """Stands in for LLMRouter: each word adds a fixed random vector, so texts that share
    words are similar, as they would be under a real encoder."""

    def __init__(self) -> None:
        self.embedded: list[str] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        out = []
        for t in texts:
            vec = np.zeros(64)
            for word in t.lower().split():
                vec += np.random.default_rng(zlib.crc32(word.encode("utf-8"))).standard_normal(64)
            out.append(vec.tolist())
        return out


class FakeCouncil:
    institution_id = "inst_health"

    def __init__(self, verdict: str) -> None:
        self.verdict = verdict

    async def deliberate(self, ctx, router):
        yield DebateTurn("d_test", self.institution_id, "synthesizer", "Synth", self.verdict, 0, True)


def _engine(monkeypatch, *, use_llm: bool, personas=None) -> Engine:
    monkeypatch.setattr(engine_mod, "get_router", FakeRouter)
    eng = Engine(personas=personas or SEED_CITIZENS[:3], seed=42, use_llm=use_llm)
    eng._spawn = lambda coro: coro.close()   # no background debates in these tests
    return eng


def _memories(eng: Engine, kind: str):
    return [m for c in eng.citizens.values() for m in c.memory.memories.values() if m.kind == kind]


@pytest.mark.parametrize("use_llm", [False, True])
async def test_crisis_observations_and_event_are_embedded(monkeypatch, use_llm):
    eng = _engine(monkeypatch, use_llm=use_llm)
    crisis = await eng.inject_crisis(
        CRISIS_TEMPLATES["pandemic"].description, "inst_health", template_key="pandemic"
    )
    observations = _memories(eng, "event")
    assert len(observations) == 3
    assert all(m.embedding is not None for m in observations)
    assert eng.causal_graph.get_event(crisis.causal_event_id)["embedding"] is not None
    if use_llm:
        assert crisis.text in eng._router.embedded


async def test_generic_observation_reaches_causal_boost_without_llm(monkeypatch):
    # An occupation with no occupation-specific line gets the template's generic observation.
    # Drought, not pandemic: pandemic's observation shares too few words with its description
    # (0.18) to clear the lexical threshold, the one template of seven that misses.
    farmer = replace(SEED_CITIZENS[0], id="zed", occupation="farmer")
    eng = _engine(monkeypatch, use_llm=False, personas=[farmer])
    drought = CRISIS_TEMPLATES["drought"]
    crisis = await eng.inject_crisis(drought.description, drought.primary_institution, template_key="drought")
    (memory,) = _memories(eng, "event")
    assert memory.text == drought.citizen_observation
    boost = eng.tcmf._causal_boost_for_memory(memory, {crisis.causal_event_id: 1.0}, 1.0)
    assert boost > 0


@pytest.mark.parametrize("use_llm", [False, True])
async def test_verdict_memories_reach_causal_boost(monkeypatch, use_llm):
    eng = _engine(monkeypatch, use_llm=use_llm)
    seen_router = []
    real_retrieve = eng.tcmf.retrieve

    async def spy(*args, **kwargs):
        seen_router.append(kwargs.get("router"))
        return await real_retrieve(*args, **kwargs)

    eng.tcmf.retrieve = spy
    crisis = await eng.inject_crisis(
        CRISIS_TEMPLATES["pandemic"].description, "inst_health", template_key="pandemic"
    )
    verdict = "The council mandates clinic reopening with safety protocols and daily case reporting."
    await eng._run_debate(crisis, FakeCouncil(verdict), None)

    assert seen_router and seen_router[0] is not None
    decision_id = f"dec_{crisis.id}"
    assert eng.causal_graph.get_event(decision_id)["embedding"] is not None
    decisions = _memories(eng, "decision")
    assert len(decisions) == 3
    for memory in decisions:
        boost = eng.tcmf._causal_boost_for_memory(memory, {decision_id: 1.0}, 1.0)
        assert boost > 0
