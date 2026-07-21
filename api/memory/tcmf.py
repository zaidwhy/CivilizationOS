"""Temporal-Causal Memory Fusion (TCMF) — the novel RAG at the core of Phase 2.

Standard RAG retrieves documents by semantic similarity. TCMF fuses two
information streams:

    1. AGORA stream  — per-citizen episodic memories scored by the generative-
                       agents formula (relevance × recency × importance).
    2. PANTHEON stream — society-wide causal graph: which past events causally
                        preceded the current crisis, and how deep in that chain?

The fused score for a citizen memory m given crisis q is the normalized-additive
combination of the two streams:

    tcmf_score(m) = normalize(episodic_score(m, q)) + lambda * causal_boost(m)

where episodic scores are min-max normalized across the candidate pool so the
causal term can compete, and causal_boost(m) = max over causal ancestors a of
[cos(emb(m), emb(a)) * depth_weight(a)] for cos >= threshold, in [0, 1]. The depth
weight rewards ancestors closer to the root cause (deeper in the chain).

Additive (not multiplicative) fusion is deliberate: a root-cause memory is
semantically far from the crisis, so its episodic score is near zero; the earlier
multiplicative form `episodic * (1 + lambda*boost)` could never lift it, because a
near-zero base stays near-zero however large the boost. Additive fusion lets the
causal signal surface such memories. See research/tcmf_paper/FINDINGS.md (F3-F7).

This rewards memories that are semantically near the causal ancestors of the
current crisis: a witness who was at the scene of the root cause outranks one who
only heard a similar-sounding symptom later.
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
        causal_boost: float = 2.0,
        causal_sim_threshold: float = 0.45,
        *,
        max_depth: int = 4,
        weak_ancestor_depth: int = 3,
        candidate_k: int = 10_000,
    ) -> None:
        self.graph = causal_graph
        # causal_boost is the additive weight (lambda) on the [0,1] causal term. It is applied
        # ADDITIVELY to a normalized episodic score, so useful values are O(1-4), not <1 as in
        # the old multiplicative form. See research/tcmf_paper/FINDINGS.md.
        self.causal_boost = causal_boost
        self.causal_sim_threshold = causal_sim_threshold
        self.max_depth = max_depth
        self.weak_ancestor_depth = weak_ancestor_depth
        # Per-citizen candidate pool. Must be large: episodic pre-filtering would drop
        # low-relevance root-cause memories BEFORE the causal boost can rescue them (fix #4).
        self.candidate_k = candidate_k

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
            ancestors = self.graph.predecessors(crisis_event_id, max_depth=self.max_depth)

        # Also include institution-scoped recent events as weak ancestors, but never the
        # crisis itself, which would leak a boost to semantically-similar distractors (fix #2).
        for ev in self.graph.events_for_institution(institution_id)[-20:]:
            eid = ev["id"]
            if eid == crisis_event_id:
                continue
            if eid not in ancestors:
                ancestors[eid] = self.weak_ancestor_depth
        ancestors.pop(crisis_event_id, None)  # a crisis is never its own ancestor

        # 3. Collect episodic memories from all citizens. Pull the full candidate pool, not a
        #    per-citizen episodic top-k, so causal-relevant but low-relevance memories survive.
        raw: list[tuple[str, ScoredMemory]] = []
        for cid, citizen in citizens.items():
            scored = citizen.memory.retrieve(
                tick, query_embedding=q_embedding, k=self.candidate_k, refresh=False
            )
            for sm in scored:
                raw.append((cid, sm))

        # 4. Normalized-additive fusion: minmax(episodic) + lambda * causal_boost (fix #1).
        max_depth_seen = max(ancestors.values(), default=1) or 1
        epi = [sm.score for _, sm in raw]
        lo, hi = (min(epi), max(epi)) if epi else (0.0, 0.0)
        span = hi - lo
        fused: list[tuple[str, Memory, float]] = []

        for cid, sm in raw:
            norm_epi = (sm.score - lo) / span if span > 1e-12 else 0.0
            depth_boost = self._causal_boost_for_memory(sm.memory, ancestors, max_depth_seen)
            score = norm_epi + self.causal_boost * depth_boost
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
                # deeper ancestors = closer to the root cause = higher weight (fix #3). The old
                # form `1 - (depth-1)/max_depth` inverted this, giving the root cause the LOWEST
                # weight and leaving it at rank ~3 even when retrieved. See FINDINGS.md (F5).
                depth_weight = depth / max(max_depth, 1)
                best = max(best, sim * depth_weight)
        return best
