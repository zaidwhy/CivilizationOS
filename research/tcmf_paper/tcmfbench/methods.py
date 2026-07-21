"""Retrieval methods under comparison, all returning a ranked list of real memory ids.

The TCMF and episodic paths drive the REAL ``api.memory.tcmf.TCMFRetriever``. The other
methods are standalone baselines operating on the same materialized memory pool, so every
method is scored on identical memory ids.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import _bootstrap  # noqa: F401  (side effect: repo root on sys.path)
from api.agents.citizen import Citizen
from api.agents.personas import Persona
from api.memory.causal_graph import CausalGraph, _cosine
from api.memory.tcmf import TCMFRetriever

from .scenario import (
    Scenario, GOLD_LABELS, CAUSAL_GOLD_LABELS, SEMANTIC_GOLD_LABELS,
)


def _persona(i: int) -> Persona:
    return Persona(
        id=f"c{i}", name=f"Citizen {i}", age=30 + i, occupation="citizen",
        traits="synthetic", backstory="benchmark agent",
        workplace_id="none", favorite_commons="none",
        home_x=0, home_y=0, sociability=0.5,
    )


@dataclass
class Materialized:
    scenario: Scenario
    citizens: dict[str, Citizen]
    graph: CausalGraph
    # real_id -> record
    mem: dict[str, dict] = field(default_factory=dict)
    all_ids: list[str] = field(default_factory=list)
    gold_ids: set[str] = field(default_factory=set)
    gold_causal: set[str] = field(default_factory=set)
    gold_semantic: set[str] = field(default_factory=set)
    root_id: str | None = None


class MappingRouter:
    """Minimal async router: embeds any text to the scenario's crisis query embedding."""

    def __init__(self, query_embedding: list[float]) -> None:
        self._q = query_embedding

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._q for _ in texts]


def materialize(sc: Scenario, max_mem_per_citizen: int = 8) -> Materialized:
    n_citizens = max(3, math.ceil(len(sc.memories) / max_mem_per_citizen))
    citizens = {p.id: Citizen(p) for p in (_persona(i) for i in range(n_citizens))}
    cids = list(citizens)

    mat = Materialized(scenario=sc, citizens=citizens, graph=CausalGraph())

    # insert memories round-robin so no citizen exceeds its per-citizen cap
    for j, spec in enumerate(sc.memories):
        cid = cids[j % n_citizens]
        m = citizens[cid].memory.add(
            spec.text, spec.tick, kind="observation",
            importance=spec.importance, embedding=spec.embedding,
        )
        spec.id = m.id
        spec.citizen_id = cid
        mat.mem[m.id] = {
            "embedding": spec.embedding, "importance": spec.importance,
            "tick": spec.tick, "label": spec.label, "topic": spec.topic,
            "citizen_id": cid, "text": spec.text,
        }
        mat.all_ids.append(m.id)
        if spec.label in GOLD_LABELS:
            mat.gold_ids.add(m.id)
        if spec.label in CAUSAL_GOLD_LABELS:
            mat.gold_causal.add(m.id)
        if spec.label in SEMANTIC_GOLD_LABELS:
            mat.gold_semantic.add(m.id)
        if spec.label == "gold_root":
            mat.root_id = m.id

    sc.gold_memory_ids = set(mat.gold_ids)
    sc.root_cause_memory_id = mat.root_id

    # build the real causal graph
    for ev in sc.events:
        mat.graph.add_event(
            ev.id, ev.text, ev.tick, kind=ev.kind,
            institution_id=ev.institution_id, embedding=ev.embedding,
        )
    for cause, effect in sc.edges:
        mat.graph.link(cause, effect)

    return mat


# --------------------------------------------------------------------------- baselines

def rank_random(mat: Materialized, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    ids = list(mat.all_ids)
    rng.shuffle(ids)
    return ids


def rank_recency(mat: Materialized) -> list[str]:
    return sorted(mat.all_ids, key=lambda i: mat.mem[i]["tick"], reverse=True)


def rank_semantic(mat: Materialized) -> list[str]:
    q = mat.scenario.query_embedding
    return sorted(mat.all_ids, key=lambda i: _cosine(mat.mem[i]["embedding"], q), reverse=True)


def _ancestor_map(mat: Materialized, clean: bool = False) -> dict[str, int]:
    """Ancestor set for the causal boost.

    ``clean=False`` reproduces the SHIPPED TCMF set: true BFS predecessors PLUS the
    institution-scoped weak-ancestor fallback (which, note, includes the crisis event
    itself at depth 3 and thereby leaks a boost to semantically-similar distractors).
    ``clean=True`` uses only the true BFS causal ancestors of the crisis.
    """
    sc = mat.scenario
    ancestors = mat.graph.predecessors(sc.crisis_event_id, max_depth=4)
    if not clean:
        for ev in mat.graph.events_for_institution(sc.institution_id)[-20:]:
            ancestors.setdefault(ev["id"], 3)
    ancestors.pop(sc.crisis_event_id, None)  # a crisis is never its own ancestor
    return ancestors


def _depth_weight(depth: int, max_depth: int, favor_root: bool) -> float:
    """Depth-to-weight map. ``favor_root=False`` reproduces the SHIPPED formula
    (direct cause depth=1 -> 1.0, deeper -> less), so the root cause, being the deepest
    ancestor, gets the LOWEST weight. ``favor_root=True`` inverts it (deeper -> more), which
    matches the module docstring's stated intent of rewarding proximity to the root cause."""
    md = max(max_depth, 1)
    if favor_root:
        return depth / md
    return 1.0 - (depth - 1) / md


def _boost(emb: list[float], ancestors: dict[str, int], graph, threshold: float,
           max_depth: int, favor_root: bool = False) -> float:
    """Max depth-weighted causal boost of a memory embedding over the ancestor set.
    This is the single source of truth shared by causal_only and every fusion variant."""
    best = 0.0
    for eid, depth in ancestors.items():
        ev = graph.get_event(eid)
        if not ev or ev.get("embedding") is None:
            continue
        sim = _cosine(emb, ev["embedding"])
        if sim >= threshold:
            best = max(best, sim * _depth_weight(depth, max_depth, favor_root))
    return best


def rank_causal_only(mat: Materialized, threshold: float = 0.45, clean: bool = False,
                     favor_root: bool = False) -> list[str]:
    ancestors = _ancestor_map(mat, clean=clean)
    max_depth = max(ancestors.values(), default=1) or 1
    key = {i: _boost(mat.mem[i]["embedding"], ancestors, mat.graph, threshold, max_depth,
                     favor_root) for i in mat.all_ids}
    return sorted(mat.all_ids, key=lambda i: key[i], reverse=True)


def _personalized_pagerank(
    nodes: list[str], edges: list[tuple[str, str]], pers: dict[str, float],
    alpha: float = 0.85, iters: int = 100, tol: float = 1e-9,
) -> dict[str, float]:
    """Power-iteration PPR on the undirected view; dangling mass teleports to pers."""
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    A = np.zeros((n, n), dtype=np.float64)
    for a, b in edges:
        A[idx[a], idx[b]] = 1.0
        A[idx[b], idx[a]] = 1.0
    deg = A.sum(axis=1)
    p = np.array([pers[nd] for nd in nodes], dtype=np.float64)
    p = p / (p.sum() or 1.0)
    r = p.copy()
    for _ in range(iters):
        newr = (1.0 - alpha) * p.copy()
        for j in range(n):
            if deg[j] > 0:
                newr += alpha * r[j] * (A[j] / deg[j])
            else:
                newr += alpha * r[j] * p  # dangling node -> teleport
        if np.abs(newr - r).sum() < tol:
            r = newr
            break
        r = newr
    return {nd: float(r[idx[nd]]) for nd in nodes}


def rank_graph_ppr(mat: Materialized, alpha: float = 0.85) -> list[str]:
    """HippoRAG-style: personalized PageRank over the event graph seeded by query
    similarity, then score memories by PPR-weighted proximity to events."""
    sc = mat.scenario
    node_ids = [ev.id for ev in sc.events]
    # personalization from query->event similarity (softmax over positive cosine)
    sims = {ev.id: max(0.0, _cosine(sc.query_embedding, ev.embedding)) for ev in sc.events}
    exp = {k: math.exp(4.0 * v) for k, v in sims.items()}
    total = sum(exp.values()) or 1.0
    pers = {k: v / total for k, v in exp.items()}
    ppr = _personalized_pagerank(node_ids, list(sc.edges), pers, alpha=alpha)

    ev_emb = {ev.id: ev.embedding for ev in sc.events}

    def score(i: str) -> float:
        emb = mat.mem[i]["embedding"]
        return max(
            (ppr.get(eid, 0.0) * max(0.0, _cosine(emb, e)) for eid, e in ev_emb.items()),
            default=0.0,
        )

    return sorted(mat.all_ids, key=score, reverse=True)


# ----------------------------------------------------------------- real TCMF pipeline

async def rank_tcmf(
    mat: Materialized, lam: float = 2.0, threshold: float = 0.45,
    use_crisis_id: bool = True,
) -> list[str]:
    """The REAL, shipped TCMFRetriever (post-fix: normalized-additive + favor-root)."""
    sc = mat.scenario
    retr = TCMFRetriever(mat.graph, causal_boost=lam, causal_sim_threshold=threshold)
    ctx = await retr.retrieve(
        question=sc.query_text, citizens=mat.citizens, tick=sc.events[-1].tick + 1,
        institution_id=sc.institution_id,
        crisis_event_id=sc.crisis_event_id if use_crisis_id else None,
        k=len(mat.all_ids), router=MappingRouter(sc.query_embedding),
    )
    return [mem.id for _cid, mem, _score in ctx.fused_memories]


async def rank_episodic(mat: Materialized) -> list[str]:
    """Same real pipeline with the causal stream switched off (lambda=0)."""
    return await rank_tcmf(mat, lam=0.0, threshold=1.0, use_crisis_id=True)


def rank_tcmf_multiplicative(mat: Materialized, lam: float = 0.6, threshold: float = 0.45,
                             clean: bool = False, favor_root: bool = False) -> list[str]:
    """The ORIGINAL (pre-fix) multiplicative operator, reproduced standalone so the paper's
    before/after contrast stays reproducible after the real code is fixed: raw episodic score
    x (1 + lambda*boost). Defaults (dirty ancestors, favor-proximate) match the old shipped
    behaviour."""
    epi = _episodic_scores(mat)
    boost = _causal_boosts(mat, threshold, clean=clean, favor_root=favor_root)
    score = {i: epi.get(i, 0.0) * (1.0 + lam * boost.get(i, 0.0)) for i in mat.all_ids}
    return sorted(mat.all_ids, key=lambda i: score[i], reverse=True)


# ------------------------------------------------- fusion-operator variants (paper core)
#
# The shipped TCMF fuses multiplicatively: episodic x (1 + lambda*boost). Because a
# root-cause memory's episodic score is near zero, that form cannot lift it. These variants
# reuse the SAME real episodic scores and the SAME causal boosts, changing only how the two
# streams combine, to test whether the fusion operator is what suppresses the causal signal.

def _episodic_scores(mat: Materialized) -> dict[str, float]:
    """Per-memory episodic score from the real MemoryStream (relevance+recency+importance)."""
    q = mat.scenario.query_embedding
    tick = mat.scenario.events[-1].tick + 1
    scores: dict[str, float] = {}
    for cit in mat.citizens.values():
        for sm in cit.memory.retrieve(tick, query_embedding=q, k=10_000, refresh=False):
            scores[sm.memory.id] = sm.score
    return scores


def _causal_boosts(mat: Materialized, threshold: float, clean: bool = False,
                   favor_root: bool = False) -> dict[str, float]:
    """Per-memory causal boost, identical formula to TCMF._causal_boost_for_memory."""
    ancestors = _ancestor_map(mat, clean=clean)
    max_depth = max(ancestors.values(), default=1) or 1
    return {
        i: _boost(mat.mem[i]["embedding"], ancestors, mat.graph, threshold, max_depth, favor_root)
        for i in mat.all_ids
    }


def _minmax(d: dict[str, float]) -> dict[str, float]:
    vals = list(d.values())
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 0.0)
    if hi - lo < 1e-12:
        return {k: 0.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


def rank_tcmf_additive(mat: Materialized, lam: float = 4.0, threshold: float = 0.45,
                       clean: bool = True, favor_root: bool = False) -> list[str]:
    """Normalized additive fusion: minmax(episodic) + lambda * causal_boost."""
    epi = _minmax(_episodic_scores(mat))
    boost = _causal_boosts(mat, threshold, clean=clean, favor_root=favor_root)
    score = {i: epi.get(i, 0.0) + lam * boost.get(i, 0.0) for i in mat.all_ids}
    return sorted(mat.all_ids, key=lambda i: score[i], reverse=True)


def rank_tcmf_rrf(mat: Materialized, c: float = 10.0, threshold: float = 0.45,
                  clean: bool = True) -> list[str]:
    """Reciprocal-rank fusion of the episodic ranking and the causal ranking."""
    epi = _episodic_scores(mat)
    boost = _causal_boosts(mat, threshold, clean=clean)
    epi_rank = {i: r for r, i in enumerate(
        sorted(mat.all_ids, key=lambda i: epi.get(i, 0.0), reverse=True))}
    caus_rank = {i: r for r, i in enumerate(
        sorted(mat.all_ids, key=lambda i: boost.get(i, 0.0), reverse=True))}
    rrf = {i: 1.0 / (c + epi_rank[i] + 1) + 1.0 / (c + caus_rank[i] + 1) for i in mat.all_ids}
    return sorted(mat.all_ids, key=lambda i: rrf[i], reverse=True)
