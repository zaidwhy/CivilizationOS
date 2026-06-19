"""Temporal-Causal Memory Fusion (TCMF) — the novel RAG at the core of Phase 2.

Standard RAG retrieves documents by semantic similarity. TCMF fuses two
information streams:

    1. AGORA stream  — per-citizen episodic memories scored by the generative-
                       agents formula (relevance × recency × importance).
    2. PANTHEON stream — society-wide causal graph: which past events causally
                        preceded the current crisis, and how deep in that chain?

The fused score for a citizen memory m given crisis q is:

    tcmf_score(m) = episodic_score(m, q) × (1 + λ × causal_boost(m))

where causal_boost(m) = max causal-depth of any graph node whose embedding is
cosine-similar to m (similarity ≥ threshold), normalized to [0, 1].

This rewards memories that are semantically near the causal ancestors of the
current crisis — a witness who was at the scene of a cause outranks one who
only heard about it later.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..agents.citizen import Citizen
from ..memory.causal_graph import CausalGraph, _cosine
from ..memory.stream import Memory, ScoredMemory


@dataclass
class TCMFContext:
    question: str
    institution_id: str
    tick: int
    # fused top-k (citizen_id, memory, tcmf_score)
    fused_memories: list[tuple[str, Memory, float]] = field(default_factory=list)
    # raw causal chain summary text
    causal_chain: list[str] = field(default_factory=list)
    # ready-to-use context block for the council prompt
    context_text: str = ""


class TCMFRetriever:
    """Fuses episodic citizen memories with the society causal graph."""

    def __init__(
        self,
        causal_graph: CausalGraph,
        causal_boost: float = 0.6,
        causal_sim_threshold: float = 0.45,
    ) -> None:
        self.graph = causal_graph
        self.causal_boost = causal_boost
        self.causal_sim_threshold = causal_sim_threshold

    async def retrieve(
        self,
        question: str,
        citizens: dict[str, Citizen],
        tick: int,
        institution_id: str,
        *,
        crisis_event_id: str | None = None,
        k: int = 12,
        router=None,
    ) -> TCMFContext:
        ctx = TCMFContext(question=question, institution_id=institution_id, tick=tick)

        # 1. Embed the crisis question
        q_embedding: list[float] | None = None
        if router is not None:
            try:
                q_embedding = (await router.embed([question]))[0]
            except Exception:
                pass

        # 2. Build causal ancestor map {ancestor_id: depth}
        ancestors: dict[str, int] = {}
        if crisis_event_id:
            ancestors = self.graph.predecessors(crisis_event_id, max_depth=4)

        # Also include institution-scoped recent events as weak ancestors
        for ev in self.graph.events_for_institution(institution_id)[-20:]:
            eid = ev["id"]
            if eid not in ancestors:
                ancestors[eid] = 3  # weak depth

        # 3. Collect episodic memories from all citizens
        raw: list[tuple[str, ScoredMemory]] = []
        for cid, citizen in citizens.items():
            scored = citizen.memory.retrieve(tick, query_embedding=q_embedding, k=8, refresh=False)
            for sm in scored:
                raw.append((cid, sm))

        # 4. For each memory, compute causal boost
        max_depth_seen = max(ancestors.values(), default=1) or 1
        fused: list[tuple[str, Memory, float]] = []

        for cid, sm in raw:
            depth_boost = self._causal_boost_for_memory(sm.memory, ancestors, max_depth_seen)
            score = sm.score * (1.0 + self.causal_boost * depth_boost)
            fused.append((cid, sm.memory, score))

        # 5. Sort and deduplicate
        fused.sort(key=lambda t: t[2], reverse=True)
        seen: set[str] = set()
        top: list[tuple[str, Memory, float]] = []
        for cid, mem, sc in fused:
            if mem.id not in seen:
                seen.add(mem.id)
                top.append((cid, mem, sc))
            if len(top) >= k:
                break
        ctx.fused_memories = top

        # 6. Build causal chain text
        chain_events: list[dict] = []
        for eid, depth in sorted(ancestors.items(), key=lambda kv: kv[1]):
            ev = self.graph.get_event(eid)
            if ev:
                chain_events.append({"depth": depth, "text": ev["text"], "tick": ev["tick"]})
        chain_events.sort(key=lambda e: e["tick"])
        ctx.causal_chain = [f"[tick {e['tick']}] {e['text']}" for e in chain_events[:8]]

        # 7. Compose the council context block
        mem_lines = "\n".join(
            f"  - [{citizens[cid].p.name if cid in citizens else cid}] {mem.text} "
            f"(importance={mem.importance:.0f})"
            for cid, mem, _ in top[:8]
        )
        chain_lines = "\n".join(f"  {c}" for c in ctx.causal_chain) or "  (no prior causal record)"
        ctx.context_text = (
            f"CRISIS: {question}\n\n"
            f"CITIZEN MEMORY EVIDENCE:\n{mem_lines or '  (none)'}\n\n"
            f"CAUSAL CHAIN (temporal-causal precedents):\n{chain_lines}"
        )
        return ctx

    def _causal_boost_for_memory(
        self,
        memory: Memory,
        ancestors: dict[str, int],
        max_depth: int,
    ) -> float:
        """Returns [0, 1] causal boost for a memory based on proximity to ancestors."""
        if not ancestors or memory.embedding is None:
            return 0.0
        best = 0.0
        for eid, depth in ancestors.items():
            ev = self.graph.get_event(eid)
            if ev is None or ev.get("embedding") is None:
                continue
            sim = _cosine(memory.embedding, ev["embedding"])
            if sim >= self.causal_sim_threshold:
                # deeper ancestors = closer to root cause = higher boost
                normalized = 1.0 - (depth - 1) / max(max_depth, 1)
                best = max(best, sim * normalized)
        return best
