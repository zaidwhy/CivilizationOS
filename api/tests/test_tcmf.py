"""Tests for TCMF retrieval: causal graph + fused memory scoring."""
from __future__ import annotations

import math
import pytest

from api.memory.causal_graph import CausalGraph
from api.memory.tcmf import TCMFRetriever
from api.memory.stream import MemoryStream
from api.agents.citizen import Citizen
from api.agents.personas import SEED_CITIZENS


def _fake_embedding(seed: int, dim: int = 8) -> list[float]:
    import random
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(dim)]
    mag = sum(x**2 for x in v) ** 0.5
    return [x / mag for x in v]


# ------------------------------------------------------------------ CausalGraph

class TestCausalGraph:
    def test_add_and_get(self):
        g = CausalGraph()
        g.add_event("e1", "Drought hits farms", tick=10, kind="crisis")
        ev = g.get_event("e1")
        assert ev["text"] == "Drought hits farms"
        assert ev["tick"] == 10
        assert len(g) == 1

    def test_link_and_predecessors(self):
        g = CausalGraph()
        g.add_event("a", "Flood", tick=1)
        g.add_event("b", "Food shortage", tick=5)
        g.add_event("c", "Riots", tick=10)
        g.link("a", "b")
        g.link("b", "c")

        preds = g.predecessors("c", max_depth=4)
        assert "b" in preds and preds["b"] == 1
        assert "a" in preds and preds["a"] == 2

    def test_predecessors_depth_limit(self):
        g = CausalGraph()
        for i in range(6):
            g.add_event(f"e{i}", f"event {i}", tick=i)
        for i in range(5):
            g.link(f"e{i}", f"e{i+1}")

        preds = g.predecessors("e5", max_depth=2)
        assert "e4" in preds
        assert "e3" in preds
        assert "e2" not in preds  # beyond max_depth

    def test_semantic_search(self):
        g = CausalGraph()
        emb_a = _fake_embedding(1)
        emb_b = _fake_embedding(2)
        g.add_event("a", "crisis a", tick=1, embedding=emb_a)
        g.add_event("b", "crisis b", tick=2, embedding=emb_b)

        results = g.semantic_search(emb_a, k=2)
        assert results[0][0] == "a"  # most similar to itself

    def test_auto_link(self):
        g = CausalGraph()
        emb1 = _fake_embedding(42)
        emb2 = _fake_embedding(42)  # identical seed → sim=1.0
        g.add_event("old", "old event", tick=1, embedding=emb1)
        g.add_event("new", "new event", tick=10, embedding=emb2)
        g.auto_link_predecessors("new", window_ticks=20)

        # old → new edge should exist (high semantic similarity)
        preds = g.predecessors("new", max_depth=1)
        assert "old" in preds

    def test_no_self_link(self):
        g = CausalGraph()
        g.add_event("x", "solo", tick=1, embedding=_fake_embedding(7))
        g.auto_link_predecessors("x")
        preds = g.predecessors("x")
        assert "x" not in preds


# ------------------------------------------------------------------ TCMF retrieval

class TestTCMFRetriever:
    def _make_citizens(self) -> dict[str, Citizen]:
        return {p.id: Citizen(p) for p in SEED_CITIZENS[:3]}

    def _seed_memories(self, citizens: dict[str, Citizen], tick: int = 50) -> None:
        texts = [
            ("ava", "Plague spreading through the clinic — many patients"),
            ("ben", "Mayor dismisses disease warnings at press conference"),
            ("cleo", "Trade routes blocked due to quarantine fears"),
        ]
        embs = [_fake_embedding(i) for i in range(3)]
        for (cid, text), emb in zip(texts, embs):
            citizens[cid].memory.add(
                text, tick, kind="observation", importance=7.0, embedding=emb
            )

    @pytest.mark.asyncio
    async def test_basic_retrieval_no_router(self):
        cg = CausalGraph()
        retriever = TCMFRetriever(cg)
        citizens = self._make_citizens()
        self._seed_memories(citizens)

        ctx = await retriever.retrieve(
            question="Health crisis at the clinic",
            citizens=citizens,
            tick=60,
            institution_id="inst_health",
            router=None,
        )
        assert len(ctx.fused_memories) > 0
        assert ctx.question == "Health crisis at the clinic"
        assert "CRISIS" in ctx.context_text

    @pytest.mark.asyncio
    async def test_causal_boost_applies(self):
        """Memories near causal ancestors score higher than unrelated ones."""
        cg = CausalGraph()
        emb_crisis = _fake_embedding(42)
        emb_unrelated = _fake_embedding(99)

        # Add a causal ancestor with the same embedding as one citizen's memory
        cg.add_event("past_event", "Clinic flooded last month", tick=10, embedding=emb_crisis)

        retriever = TCMFRetriever(cg, causal_boost=1.0, causal_sim_threshold=0.3)
        citizens = self._make_citizens()

        # ava's memory has emb_crisis embedding (near the ancestor)
        citizens["ava"].memory.add(
            "Clinic flooded — we struggled", 50,
            kind="observation", importance=5.0, embedding=emb_crisis
        )
        # ben's memory is unrelated
        citizens["ben"].memory.add(
            "Had coffee", 50,
            kind="observation", importance=5.0, embedding=emb_unrelated
        )

        cg.add_event("crisis_now", "New flood at clinic", tick=60, embedding=emb_crisis)
        cg.link("past_event", "crisis_now")

        ctx = await retriever.retrieve(
            question="Flooding at clinic",
            citizens=citizens,
            tick=60,
            institution_id="inst_health",
            crisis_event_id="crisis_now",
            router=None,
        )

        # ava's boosted memory should rank first
        assert ctx.fused_memories[0][0] == "ava"

    @pytest.mark.asyncio
    async def test_empty_citizens(self):
        cg = CausalGraph()
        retriever = TCMFRetriever(cg)
        ctx = await retriever.retrieve(
            question="Ghost town crisis",
            citizens={},
            tick=1,
            institution_id="inst_gov",
            router=None,
        )
        assert ctx.fused_memories == []
        assert "CRISIS" in ctx.context_text

    @pytest.mark.asyncio
    async def test_no_embeddings_falls_back_gracefully(self):
        """Without embeddings, retrieval still returns memories by recency/importance."""
        cg = CausalGraph()
        retriever = TCMFRetriever(cg)
        citizens = self._make_citizens()
        # memories without embeddings
        citizens["ava"].memory.add("Something happened", 50, importance=8.0)
        citizens["ben"].memory.add("Another thing", 40, importance=3.0)

        ctx = await retriever.retrieve(
            question="What is going on?",
            citizens=citizens,
            tick=55,
            institution_id="inst_gov",
            router=None,
        )
        assert len(ctx.fused_memories) >= 1
