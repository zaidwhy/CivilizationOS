"""Retrieval methods under comparison, all returning a ranked list of real memory ids.

The TCMF and episodic paths drive the REAL ``api.memory.tcmf.TCMFRetriever``. The other
methods are standalone baselines operating on the same materialized memory pool, so every
method is scored on identical memory ids.
"""
from __future__ import annotations

import math
import re
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


def distractor_ids(mat: Materialized) -> set[str]:
    """Ids of memories labeled `distractor` - causally irrelevant, semantically loud. A false
    ancestor edge (N04) should never earn these a causal boost, so any of them surfacing in a
    top-k is precision-side damage, not a ranking nuance."""
    return {i for i in mat.all_ids if mat.mem[i]["label"] == "distractor"}


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


def _ancestor_map(mat: Materialized, clean: bool = False, max_depth: int = 4) -> dict[str, int]:
    """Ancestor set for the causal boost.

    ``clean=False`` reproduces the SHIPPED TCMF set: true BFS predecessors PLUS the
    institution-scoped weak-ancestor fallback (which, note, includes the crisis event
    itself at depth 3 and thereby leaks a boost to semantically-similar distractors).
    ``clean=True`` uses only the true BFS causal ancestors of the crisis. ``max_depth``
    (default 4, matching ``TCMFRetriever``'s own default) is the BFS depth cap - exposed as a
    parameter so N12 can sweep it; every existing caller keeps the old hardcoded value.
    """
    sc = mat.scenario
    ancestors = mat.graph.predecessors(sc.crisis_event_id, max_depth=max_depth)
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
                   favor_root: bool = False, bfs_depth_cap: int = 4) -> dict[str, float]:
    """Per-memory causal boost, identical formula to TCMF._causal_boost_for_memory.
    ``bfs_depth_cap`` is the ancestor-search depth limit (N12 sweep parameter); every existing
    caller keeps the default, matching ``TCMFRetriever``'s own hardcoded value."""
    ancestors = _ancestor_map(mat, clean=clean, max_depth=bfs_depth_cap)
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


def _prune_pool(mat: Materialized, epi: dict[str, float], prune_k: int | None) -> tuple[list[str], list[str]]:
    """Reproduce fix #4's OLD defect: a per-citizen top-``prune_k`` cut on RAW episodic score,
    applied BEFORE the causal boost ever sees the rest of the pool - exactly what
    ``MemoryStream.retrieve(..., k=candidate_k)`` did with the old default before
    ``TCMFRetriever.candidate_k`` was raised to 10,000 (see ``api/memory/tcmf.py``).
    ``prune_k=None`` reproduces the fix (full pool, nothing dropped). Returns
    ``(kept_ids, pruned_ids)``; pruned memories can never be recovered by any fusion score,
    matching the real bug."""
    if prune_k is None:
        return list(mat.all_ids), []
    by_citizen: dict[str, list[str]] = {}
    for i in mat.all_ids:
        by_citizen.setdefault(mat.mem[i]["citizen_id"], []).append(i)
    kept: set[str] = set()
    for ids in by_citizen.values():
        kept.update(sorted(ids, key=lambda i: epi.get(i, 0.0), reverse=True)[:prune_k])
    return [i for i in mat.all_ids if i in kept], [i for i in mat.all_ids if i not in kept]


def rank_tcmf_ablation(
    mat: Materialized, *, additive: bool = True, clean: bool = True, favor_root: bool = True,
    prune_k: int | None = None, lam: float = 4.0, threshold: float = 0.45, bfs_depth_cap: int = 4,
) -> list[str]:
    """N12: leave-one-out ablation of the four shipped fixes, independently toggleable, on the
    SAME episodic scores and causal boosts every other variant in this module uses (only the
    toggled mechanism changes). ``additive=True, clean=True, favor_root=True, prune_k=None`` is
    the full (shipped) method; flip exactly one flag to measure that fix's individual
    contribution, or several at once to measure interaction (N06/F8: (1) and (3) are the pair
    the paper's own decision-quality result suggests interact).

        fix 1 (operator):     additive=False  -> the old multiplicative form
        fix 2 (ancestor leak): clean=False     -> crisis leaks into its own ancestor set
        fix 3 (depth weight):  favor_root=False -> favors the proximate cause, not the root
        fix 4 (pre-fusion prune): prune_k=int  -> per-citizen top-k cut before fusion
    """
    epi_full = _episodic_scores(mat)
    pool_ids, pruned_ids = _prune_pool(mat, epi_full, prune_k)
    boost_full = _causal_boosts(mat, threshold, clean=clean, favor_root=favor_root,
                                bfs_depth_cap=bfs_depth_cap)

    if additive:
        epi_n = _minmax({i: epi_full[i] for i in pool_ids})
        score = {i: epi_n.get(i, 0.0) + lam * boost_full.get(i, 0.0) for i in pool_ids}
    else:
        score = {i: epi_full.get(i, 0.0) * (1.0 + lam * boost_full.get(i, 0.0)) for i in pool_ids}

    ranked = sorted(pool_ids, key=lambda i: score[i], reverse=True)
    return ranked + pruned_ids


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


# ---------------------------------------------------------------- N07: additional baselines
#
# Reimplementable *mechanisms*, not system reimplementations - named "X-style mechanism" in
# both code and prose, the same correction already applied to graph_ppr/HippoRAG. These test
# whether the causal-ancestor effect is an artifact of dense-embedding retrieval specifically
# (MMR, community-summary), of embeddings at all (BM25), or survives against the context-
# management mechanisms real long-running agents actually ship (summary-buffer,
# extract-and-consolidate).

def rank_mmr(mat: Materialized, mmr_lambda: float = 0.5) -> list[str]:
    """Maximal marginal relevance: the standard diversity re-ranker. Iteratively picks the
    candidate maximizing ``mmr_lambda*sim(query) - (1-mmr_lambda)*max_sim(already selected)``,
    vectorized via a precomputed pairwise-cosine matrix. Tests whether plain diversification
    (pushing past redundant high-similarity distractors, no causal signal at all) already
    surfaces causal ancestors. ``mmr_lambda=1.0`` degenerates to pure relevance ranking
    (identical to ``rank_semantic``) - asserted in ``test_n07_baselines.py``."""
    ids = list(mat.all_ids)
    n = len(ids)
    if n == 0:
        return []
    E = np.asarray([mat.mem[i]["embedding"] for i in ids], dtype=np.float64)
    norms = np.linalg.norm(E, axis=1)
    norms[norms == 0] = 1.0
    En = E / norms[:, None]
    q = np.asarray(mat.scenario.query_embedding, dtype=np.float64)
    qn = q / (np.linalg.norm(q) or 1.0)
    qsim = En @ qn
    S = En @ En.T

    selected = np.zeros(n, dtype=bool)
    max_sel_sim = np.zeros(n, dtype=np.float64)  # no selection yet -> diversity term 0
    order: list[str] = []
    for _ in range(n):
        score = mmr_lambda * qsim - (1.0 - mmr_lambda) * max_sel_sim
        score = np.where(selected, -np.inf, score)
        best = int(np.argmax(score))
        order.append(ids[best])
        selected[best] = True
        max_sel_sim = np.maximum(max_sel_sim, S[best])
    return order


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def rank_bm25(mat: Materialized, k1: float = 1.5, b: float = 0.75) -> list[str]:
    """BM25 lexical ranking of memory text against the query text - the standard sparse-
    retrieval baseline, computed with no embeddings at all. Tests whether the causal-ancestor
    effect is an artifact of dense retrieval specifically, or survives (or fails) under pure
    term-overlap scoring."""
    ids = list(mat.all_ids)
    n_docs = len(ids)
    if n_docs == 0:
        return []
    docs = {i: _tokenize(mat.mem[i]["text"]) for i in ids}
    doc_len = {i: len(docs[i]) for i in ids}
    avgdl = (sum(doc_len.values()) / n_docs) or 1.0

    df: dict[str, int] = {}
    for i in ids:
        for term in set(docs[i]):
            df[term] = df.get(term, 0) + 1
    idf = {t: math.log(1.0 + (n_docs - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    q_terms = _tokenize(mat.scenario.query_text)

    def score(i: str) -> float:
        tf: dict[str, int] = {}
        for t in docs[i]:
            tf[t] = tf.get(t, 0) + 1
        dl = doc_len[i]
        s = 0.0
        for t in q_terms:
            f = tf.get(t, 0)
            if f == 0:
                continue
            s += idf.get(t, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        return s

    return sorted(ids, key=score, reverse=True)


def rank_summary_buffer(mat: Materialized, recent_window: int = 10, page_size: int = 10) -> list[str]:
    """Summary-buffer / paging retrieval, a MemGPT-style mechanism: the most recent
    ``recent_window`` memories stay in the working context and are read first (as MemGPT's
    recall storage keeps recent turns in-context), everything older is chunked into fixed-size,
    time-ordered pages, each page is represented by a single averaged embedding standing in
    for an LLM-written page summary, and pages are pulled in order of that summary's
    similarity to the query (memories within a page keep their recency order). Tests whether
    an agent's ordinary context-management paging - no causal graph, no re-ranking within the
    recent window - already surfaces causal ancestors."""
    ids_by_recency = sorted(mat.all_ids, key=lambda i: mat.mem[i]["tick"], reverse=True)
    recent = ids_by_recency[:recent_window]
    older = ids_by_recency[recent_window:]

    q = mat.scenario.query_embedding
    pages = [older[j:j + page_size] for j in range(0, len(older), page_size)]

    def page_summary_sim(page: list[str]) -> float:
        embs = np.asarray([mat.mem[i]["embedding"] for i in page], dtype=np.float64)
        centroid = embs.mean(axis=0).tolist()
        return _cosine(centroid, q)

    pages_ranked = sorted(pages, key=page_summary_sim, reverse=True)
    return recent + [i for page in pages_ranked for i in page]


def _kmeans(X: np.ndarray, k: int, seed: int, iters: int = 50) -> np.ndarray:
    """Minimal seeded Lloyd's-algorithm k-means, pure numpy. Returns a cluster label per row."""
    n = X.shape[0]
    k = max(1, min(k, n))
    rng = np.random.default_rng(seed)
    init_idx = rng.choice(n, size=k, replace=False)
    centroids = X[init_idx].copy()
    labels = np.full(n, -1, dtype=int)
    for _ in range(iters):
        d = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(d, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for c in range(k):
            members = X[labels == c]
            if len(members):
                centroids[c] = members.mean(axis=0)
    return labels


def rank_community_summary(mat: Materialized, n_communities: int = 6, seed: int = 0) -> list[str]:
    """Community-summary retrieval, a GraphRAG-style mechanism: cluster the memory pool into
    communities (seeded k-means on embeddings stands in for GraphRAG's graph-community
    detection - there is no LLM here to write prose summaries, so each community's centroid
    stands in for one), rank communities by summary-to-query similarity, then rank memories
    within a community by their own query similarity. Tests whether retrieving via cluster
    summaries - no per-edge causal traversal - already surfaces causal ancestors."""
    ids = list(mat.all_ids)
    if not ids:
        return []
    E = np.asarray([mat.mem[i]["embedding"] for i in ids], dtype=np.float64)
    labels = _kmeans(E, n_communities, seed=seed)
    q = mat.scenario.query_embedding

    communities: dict[int, list[str]] = {}
    for idx, i in enumerate(ids):
        communities.setdefault(int(labels[idx]), []).append(i)

    def centroid_sim(members: list[str]) -> float:
        embs = np.asarray([mat.mem[i]["embedding"] for i in members], dtype=np.float64)
        centroid = embs.mean(axis=0).tolist()
        return _cosine(centroid, q)

    ranked_communities = sorted(communities.values(), key=centroid_sim, reverse=True)
    out: list[str] = []
    for members in ranked_communities:
        out.extend(sorted(members, key=lambda i: _cosine(mat.mem[i]["embedding"], q), reverse=True))
    return out


def rank_extract_consolidate(mat: Materialized, dedup_threshold: float = 0.92) -> list[str]:
    """Extract-and-consolidate memory, a Mem0-style mechanism: greedily merge near-duplicate
    memories (pairwise cosine >= ``dedup_threshold``) into groups before ranking - the dedup/
    merge step Mem0 performs to keep memory compact, approximated here without an LLM by
    embedding-similarity clustering (single-pass, deterministic: each memory joins the first
    existing group whose representative it is similar enough to, else starts a new group).
    Each group's representative (its highest-importance member, standing in for the
    consolidated/extracted memory) is ranked by query similarity; the rest of the group trails
    immediately after in importance order. Tests whether deduping the pool before ranking helps
    (removing near-duplicate distractors competing for top-k slots) or hurts (merging a true
    ancestor's rank into a distractor-dominated group) causal-ancestor recall."""
    ids = list(mat.all_ids)
    n = len(ids)
    if n == 0:
        return []
    E = np.asarray([mat.mem[i]["embedding"] for i in ids], dtype=np.float64)
    norms = np.linalg.norm(E, axis=1)
    norms[norms == 0] = 1.0
    En = E / norms[:, None]
    S = En @ En.T

    group_reps_idx: list[int] = []
    groups: list[list[str]] = []
    for idx, i in enumerate(ids):
        placed = False
        for gidx, rep_idx in enumerate(group_reps_idx):
            if S[idx, rep_idx] >= dedup_threshold:
                groups[gidx].append(i)
                placed = True
                break
        if not placed:
            groups.append([i])
            group_reps_idx.append(idx)

    q = mat.scenario.query_embedding

    def representative(members: list[str]) -> str:
        return max(members, key=lambda i: mat.mem[i]["importance"])

    reps = {gidx: representative(members) for gidx, members in enumerate(groups)}
    group_order = sorted(
        range(len(groups)),
        key=lambda gidx: _cosine(mat.mem[reps[gidx]]["embedding"], q),
        reverse=True,
    )

    out: list[str] = []
    for gidx in group_order:
        rep = reps[gidx]
        rest = sorted(
            (i for i in groups[gidx] if i != rep),
            key=lambda i: mat.mem[i]["importance"], reverse=True,
        )
        out.append(rep)
        out.extend(rest)
    return out
