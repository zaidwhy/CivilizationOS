"""Competing memory retrievers, written from scratch for this audit.

Every function returns a full ranking of memory indices, best first. None of the baselines has
a tuned parameter: constants below were fixed before the first run and are listed in PREREG.md
by reference to this file.

TCMF appears twice. ``tcmf_deployed`` calls the production class untouched and is the only
source of headline TCMF numbers. ``tcmf_variant`` is a vectorized re-implementation with knobs,
used for ablations only, and is held to ranking parity with the production class by a test.
"""
from __future__ import annotations

import asyncio

import numpy as np

from api.agents.citizen import Citizen
from api.agents.personas import Persona
from api.memory.tcmf import TCMFRetriever

from .graphs import INSTITUTION, ObservedGraph, ancestors, event_id, to_causal_graph
from .world import World

RECENCY_DECAY = 0.02          # MemoryStream's default, restated for the re-implementation
WEAK_ANCESTOR_WINDOW = 20     # TCMFRetriever: the institution's last 20 events
PPR_DAMPING = 0.5
PPR_MEMORY_EDGE_MIN = 0.30
HOP_FRONTIER = 10


def _order(scores: np.ndarray) -> list[int]:
    return [int(i) for i in np.argsort(-scores, kind="stable")]


def _interleave(first: list[int], second: list[int]) -> list[int]:
    out, seen = [], set()
    for a, b in zip(first, second):
        for i in (a, b):
            if i not in seen:
                seen.add(i)
                out.append(i)
    return out


def rank_random(world: World, og: ObservedGraph, seed: int = 0) -> list[int]:
    return [int(i) for i in np.random.default_rng(seed).permutation(world.n)]


def rank_oracle(world: World, og: ObservedGraph) -> list[int]:
    gold = world.causal_gold
    root = world.root_gold
    return sorted(range(world.n), key=lambda i: (i not in root, i not in gold))


def rank_chronological(world: World, og: ObservedGraph) -> list[int]:
    """A sliding window: the newest memories are what the agent still holds."""
    return _order(world.mem_tick.astype(float))


def _similarity(world: World) -> np.ndarray:
    return world.mem_emb @ world.query


def rank_vector(world: World, og: ObservedGraph) -> list[int]:
    return _order(_similarity(world))


def _episodic(world: World, relevance: bool = True, recency: bool = True,
              importance: bool = True) -> np.ndarray:
    score = np.zeros(world.n)
    if relevance:
        score += np.maximum(0.0, _similarity(world))
    if recency:
        score += np.exp(-RECENCY_DECAY * np.maximum(0, world.cfg.now - world.mem_tick))
    if importance:
        score += world.mem_imp / 10.0
    return score


def rank_episodic(world: World, og: ObservedGraph) -> list[int]:
    """Generative-agents score: relevance + recency + importance."""
    return _order(_episodic(world))


def _ancestor_similarity(world: World, og: ObservedGraph) -> np.ndarray:
    anc = list(ancestors(og))
    if not anc:
        return np.zeros(world.n)
    return (world.mem_emb @ world.ev_emb[anc].T).max(axis=1)


def rank_graph_query(world: World, og: ObservedGraph) -> list[int]:
    """Graph memory with no fusion: each ancestor event is a query; a memory scores its best
    match. No threshold, no depth weight, no episodic term."""
    return _order(_ancestor_similarity(world, og))


def rank_graph_union(world: World, og: ObservedGraph) -> list[int]:
    """Alternate between the graph-query list and the plain vector list."""
    if not ancestors(og):
        return rank_vector(world, og)
    return _interleave(rank_graph_query(world, og), rank_vector(world, og))


def rank_event_log(world: World, og: ObservedGraph) -> list[int]:
    """Added after the first run (see PREREG deviations). Uses the event log but no edges:
    a memory scores its best match to ANY logged event other than the crisis. If TCMF does no
    better than this, the causal edges are not what is finding the cause."""
    events = [e for e in og.nodes if e != world.crisis]
    return _order((world.mem_emb @ world.ev_emb[events].T).max(axis=1))


def rank_event_log_union(world: World, og: ObservedGraph) -> list[int]:
    return _interleave(rank_event_log(world, og), rank_vector(world, og))


def rank_graph_ppr(world: World, og: ObservedGraph) -> list[int]:
    """Personalized PageRank over events and memories (HippoRAG-style). Event edges are walked
    in both directions; a memory attaches to its nearest event when similar enough."""
    events = list(og.nodes)
    pos = {e: i for i, e in enumerate(events)}
    n_ev, n = len(events), len(events) + world.n
    adj = np.zeros((n, n))
    for cause, effect in og.edges:
        adj[pos[cause], pos[effect]] = adj[pos[effect], pos[cause]] = 1.0
    sims = world.mem_emb @ world.ev_emb[events].T
    nearest = sims.argmax(axis=1)
    for m in range(world.n):
        w = sims[m, nearest[m]]
        if w >= PPR_MEMORY_EDGE_MIN:
            adj[n_ev + m, nearest[m]] = adj[nearest[m], n_ev + m] = w
    seed = np.zeros(n)
    relevance = np.maximum(0.0, _similarity(world))
    if og.crisis is not None:
        seed[pos[og.crisis]] = 0.5
        seed[n_ev:] = 0.5 * relevance / relevance.sum()
    else:
        seed[n_ev:] = relevance / relevance.sum()
    out_weight = adj.sum(axis=1, keepdims=True)
    transition = np.divide(adj, out_weight, out=np.zeros_like(adj), where=out_weight > 0)
    rank = seed.copy()
    for _ in range(50):
        rank = (1 - PPR_DAMPING) * seed + PPR_DAMPING * (transition.T @ rank)
    return _order(rank[n_ev:])


def rank_two_hop(world: World, og: ObservedGraph) -> list[int]:
    """Graph-free multi-hop. Each of the top matches proposes a second query made of what it
    says beyond the question (its residual after removing the query direction); a memory
    scores its best match to any proposal, weighted by how relevant the proposer was. The
    result alternates with the plain vector list. Uses no graph at all."""
    sim = _similarity(world)
    frontier = np.argsort(-sim, kind="stable")[:HOP_FRONTIER]
    residual = world.mem_emb[frontier] - np.outer(sim[frontier], world.query)
    norms = np.linalg.norm(residual, axis=1, keepdims=True)
    residual = residual / np.where(norms > 1e-9, norms, 1.0)
    hop = (world.mem_emb @ residual.T) * np.maximum(0.0, sim[frontier])
    for col, f in enumerate(frontier):
        hop[f, col] = 0.0  # a memory does not vouch for itself
    return _interleave(_order(hop.max(axis=1)), rank_vector(world, og))


class _QueryRouter:
    def __init__(self, query: np.ndarray) -> None:
        self._query = query.tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._query for _ in texts]


def _persona(i: int) -> Persona:
    return Persona(
        id=f"c{i}", name=f"Citizen {i}", age=30, occupation="citizen", traits="",
        backstory="", workplace_id="none", favorite_commons="none",
        home_x=0, home_y=0, sociability=0.5,
    )


def prepare_tcmf_deployed(world: World, og: ObservedGraph, *, n_citizens: int = 5,
                          mem_text: list[str] | None = None, ev_text: list[str] | None = None,
                          **retriever_kwargs):
    """Load the world into production objects. Returns a zero-argument-per-query ``retrieve(k)``
    and the map from production memory id to this world's memory index."""
    citizens = {f"c{i}": Citizen(_persona(i)) for i in range(n_citizens)}
    index_of: dict[str, int] = {}
    for j in range(world.n):
        mem = citizens[f"c{j % n_citizens}"].memory.add(
            mem_text[j] if mem_text else world.mem_label[j], int(world.mem_tick[j]),
            importance=float(world.mem_imp[j]), embedding=world.mem_emb[j].tolist(),
        )
        index_of[mem.id] = j
    retriever = TCMFRetriever(to_causal_graph(world, og, ev_text), **retriever_kwargs)
    router = _QueryRouter(world.query)
    crisis_id = event_id(og.crisis) if og.crisis is not None else None

    def retrieve(k: int):
        return asyncio.run(retriever.retrieve(
            "crisis", citizens, world.cfg.now, INSTITUTION,
            crisis_event_id=crisis_id, k=k, router=router,
        ))

    return retrieve, index_of


def run_tcmf_deployed(world: World, og: ObservedGraph, *, k: int, **kwargs):
    """One call to the production ``TCMFRetriever.retrieve``: its context object and id map."""
    retrieve, index_of = prepare_tcmf_deployed(world, og, **kwargs)
    return retrieve(k), index_of


def rank_tcmf_deployed(world: World, og: ObservedGraph, **retriever_kwargs) -> list[int]:
    """The production retriever with its shipped defaults, asked for the whole ranking."""
    ctx, index_of = run_tcmf_deployed(world, og, k=world.n, **retriever_kwargs)
    return [index_of[mem.id] for _, mem, _ in ctx.fused_memories]


def tcmf_ancestor_depths(world: World, og: ObservedGraph, weak: bool, max_depth: int) -> dict[int, int]:
    depths = ancestors(og, max_depth=max_depth)
    if weak:
        in_tick_order = sorted(og.nodes, key=lambda n: (int(world.ev_tick[n]), n))
        for e in in_tick_order[-WEAK_ANCESTOR_WINDOW:]:
            if e != og.crisis:
                depths.setdefault(e, 3)
    return depths


def tcmf_boost(world: World, depths: dict[int, int], threshold: float, depth_mode: str,
               aggregate: str) -> np.ndarray:
    if not depths:
        return np.zeros(world.n)
    events = list(depths)
    deepest = max(depths.values())
    d = np.array([depths[e] for e in events], dtype=float)
    weight = {"root": d / deepest, "uniform": np.ones_like(d), "proximal": 1 - (d - 1) / deepest}[depth_mode]
    sims = (world.mem_emb @ world.ev_emb[events].T).astype(np.float32)
    contrib = np.where(sims >= threshold, sims * weight, 0.0)
    return contrib.max(axis=1) if aggregate == "max" else contrib.mean(axis=1)


def tcmf_variant_scores(
    world: World, og: ObservedGraph, *, lam: float = 4.0, threshold: float = 0.45,
    depth_mode: str = "root", weak: bool = True, normalize: bool = True,
    relevance: bool = True, recency: bool = True, importance: bool = True,
    aggregate: str = "max", operator: str = "add", max_depth: int = 4,
) -> np.ndarray:
    episodic = _episodic(world, relevance, recency, importance)
    if normalize:
        span = episodic.max() - episodic.min()
        episodic = (episodic - episodic.min()) / span if span > 1e-12 else np.zeros(world.n)
    boost = tcmf_boost(world, tcmf_ancestor_depths(world, og, weak, max_depth),
                       threshold, depth_mode, aggregate)
    return episodic + lam * boost if operator == "add" else episodic * (1.0 + lam * boost)


def rank_tcmf_variant(world: World, og: ObservedGraph, **knobs) -> list[int]:
    return _order(tcmf_variant_scores(world, og, **knobs))


def rank_boosted_then_episodic(world: World, og: ObservedGraph) -> list[int]:
    """A two-stage rule with no fusion arithmetic: every memory TCMF would boost comes first
    (by boost), then everything else in episodic order. If this reproduces TCMF's top 5, the
    additive fusion at the shipped weight is a sort key, not a blend."""
    boost = tcmf_boost(world, tcmf_ancestor_depths(world, og, True, 4), 0.45, "root", "max")
    episodic = _episodic(world)
    return sorted(range(world.n), key=lambda i: (boost[i] <= 0, -boost[i], -episodic[i]))
