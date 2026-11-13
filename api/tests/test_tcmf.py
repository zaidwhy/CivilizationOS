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
            ("ava", "Plague spreading through the clinic - many patients"),
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
            "Clinic flooded - we struggled", 50,
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


# ------------------------------------------------------------------ weak ancestors

def _axis(i: int, dim: int = 16) -> list[float]:
    v = [0.0] * dim
    v[i] = 1.0
    return v


class TestWeakAncestors:
    """A recent event the graph does not link to the crisis is a fallback, never a rival to a
    linked cause. Found by research/tcmf_paper/audit: the old rule gave it depth 3, above a
    direct cause at depth 1."""

    def _world(self, chain_len: int, unrelated: int):
        """root -> ... -> crisis, plus unrelated earlier events of the same institution. Each
        event has one witness memory with the event's own embedding."""
        cg = CausalGraph()
        citizens = {p.id: Citizen(p) for p in SEED_CITIZENS[:3]}
        ids = list(citizens)
        witness_of: dict[str, str] = {}

        def add(event_id: str, axis: int, tick: int) -> None:
            cg.add_event(event_id, f"event {event_id}", tick=tick, kind="decision",
                         institution_id="inst_gov", embedding=_axis(axis))
            mem = citizens[ids[axis % 3]].memory.add(
                f"I saw {event_id}", tick, importance=5.0, embedding=_axis(axis))
            witness_of[event_id] = mem.id

        for j in range(unrelated):
            add(f"unrelated{j}", 8 + j, tick=20 + j)
        for i in range(chain_len):
            add(f"cause{i}", i, tick=40 + i)       # cause0 is the root
        cg.add_event("crisis", "the crisis", tick=90, kind="crisis",
                     institution_id="inst_gov", embedding=_axis(15))
        for i in range(chain_len):
            cg.link(f"cause{i}", f"cause{i + 1}" if i + 1 < chain_len else "crisis")
        return cg, citizens, witness_of

    async def _ranking(self, cg, citizens, **kwargs) -> tuple[list[str], str]:
        ctx = await TCMFRetriever(cg, **kwargs).retrieve(
            question="why did this happen", citizens=citizens, tick=91,
            institution_id="inst_gov", crisis_event_id="crisis", k=50, router=None,
        )
        return [mem.id for _, mem, _ in ctx.fused_memories], ctx.context_text

    @pytest.mark.asyncio
    async def test_direct_cause_outranks_every_unlinked_event(self):
        cg, citizens, witness_of = self._world(chain_len=1, unrelated=6)
        ranking, _ = await self._ranking(cg, citizens)
        assert ranking[0] == witness_of["cause0"]

    @pytest.mark.asyncio
    async def test_every_linked_cause_outranks_every_unlinked_event(self):
        cg, citizens, witness_of = self._world(chain_len=3, unrelated=6)
        ranking, _ = await self._ranking(cg, citizens)
        causes = {witness_of[f"cause{i}"] for i in range(3)}
        assert set(ranking[:3]) == causes
        assert ranking[0] == witness_of["cause0"], "the root cause ranks first"

    @pytest.mark.asyncio
    async def test_unlinked_events_still_rank_above_unmatched_memories(self):
        """The fallback survives: with no edges at all, event witnesses beat background."""
        cg, citizens, witness_of = self._world(chain_len=0, unrelated=4)
        background = citizens["ava"].memory.add("weather was fine", 60, importance=5.0,
                                                embedding=_axis(7))
        ranking, _ = await self._ranking(cg, citizens)
        assert ranking.index(background.id) == len(ranking) - 1

    @pytest.mark.asyncio
    async def test_root_six_hops_back_is_reached(self):
        cg, citizens, witness_of = self._world(chain_len=6, unrelated=2)
        ranking, _ = await self._ranking(cg, citizens)
        assert ranking[0] == witness_of["cause0"]

    @pytest.mark.asyncio
    async def test_causal_chain_text_still_lists_weak_ancestors(self):
        """Narrowing the chain to linked events was measured and reverted: it misleads the
        reader whenever the linker's edges are wrong. See the comment at step 6 of retrieve."""
        cg, citizens, _ = self._world(chain_len=2, unrelated=3)
        _, text = await self._ranking(cg, citizens)
        chain = text.split("CAUSAL CHAIN")[1]
        assert "cause0" in chain and "cause1" in chain
        assert "unrelated0" in chain

    @pytest.mark.asyncio
    async def test_old_depth_three_is_still_selectable_and_shows_the_defect(self):
        """The benchmark pins the configuration the paper measured; this is what it did."""
        cg, citizens, witness_of = self._world(chain_len=1, unrelated=6)
        ranking, _ = await self._ranking(cg, citizens, weak_ancestor_depth=3, max_depth=4)
        assert ranking.index(witness_of["cause0"]) == 6, "six unlinked events outrank the cause"
