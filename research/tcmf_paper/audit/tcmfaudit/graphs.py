"""The graph a retriever is allowed to see, kept separate from the world's latent truth.

``deployed`` is the only builder that calls production code to create edges: it replays the
events into a real ``CausalGraph`` in tick order and runs ``auto_link_predecessors`` exactly
where ``api/sim/engine.py`` runs it: on each crisis as it is injected. With the default only
the scenario's crisis is linked; ``link_all`` links every event on arrival, which is what
production does when the earlier events were themselves crises.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from api.memory.causal_graph import CausalGraph

from .world import World

INSTITUTION = "inst"


@dataclass
class ObservedGraph:
    nodes: list[int]                   # event indices present, any order
    edges: list[tuple[int, int]]       # (cause, effect)
    crisis: int | None                 # None: the retriever is not told which event is the crisis


def event_id(index: int) -> str:
    return f"e{index}"


def chain_only(world: World) -> ObservedGraph:
    """The existing benchmark's condition: only the true chain exists in the graph."""
    nodes = sorted({n for edge in world.true_edges for n in edge})
    return ObservedGraph(nodes, list(world.true_edges), world.crisis)


def oracle(world: World) -> ObservedGraph:
    """Every institution event is a node; the edges are exactly the true ones."""
    return ObservedGraph(list(range(len(world.ev_kind))), list(world.true_edges), world.crisis)


def noisy(world: World, rng: np.random.Generator, p_drop: float, n_false: int) -> ObservedGraph:
    """True edges each dropped with probability ``p_drop``; ``n_false`` edges from a decoy into
    the crisis or a true ancestor that happened after it."""
    edges = [e for e in world.true_edges if rng.random() >= p_drop]
    targets = [world.crisis] + world.events_of("anc")
    candidates = [
        (d, t) for d in world.events_of("decoy") for t in targets
        if world.ev_tick[d] < world.ev_tick[t]
    ]
    if candidates and n_false:
        picks = rng.choice(len(candidates), size=min(n_false, len(candidates)), replace=False)
        edges += [candidates[int(i)] for i in picks]
    return ObservedGraph(list(range(len(world.ev_kind))), edges, world.crisis)


def noisy_deep(world: World, rng: np.random.Generator, p_drop: float, n_false: int) -> ObservedGraph:
    """Like ``noisy`` but each false edge makes an unrelated earlier event a parent of the
    root, so the impostor is the deepest node. Added after review: ``noisy`` only ever makes
    decoys shallow, which a root-favouring depth weight happens to forgive."""
    edges = [e for e in world.true_edges if rng.random() >= p_drop]
    root = world.cfg.depth - 1
    earlier = [d for d in world.events_of("decoy") if world.ev_tick[d] < world.ev_tick[root]]
    if earlier and n_false:
        picks = rng.choice(len(earlier), size=min(n_false, len(earlier)), replace=False)
        edges += [(earlier[int(i)], root) for i in picks]
    return ObservedGraph(list(range(len(world.ev_kind))), edges, world.crisis)


def shuffled(world: World, rng: np.random.Generator) -> ObservedGraph:
    """Negative control: the true chain's shape, wired through unrelated decoy events."""
    decoys = world.events_of("decoy")
    depth = world.cfg.depth
    if len(decoys) < depth:
        raise ValueError("shuffled control needs at least as many decoys as chain depth")
    stand_in = [int(i) for i in rng.choice(decoys, size=depth, replace=False)]
    path = stand_in + [world.crisis]
    edges = [(path[i], path[i + 1]) for i in range(depth)]
    return ObservedGraph(list(range(len(world.ev_kind))), edges, world.crisis)


def no_crisis_id(world: World) -> ObservedGraph:
    return ObservedGraph(list(range(len(world.ev_kind))), list(world.true_edges), None)


def to_causal_graph(world: World, og: ObservedGraph, ev_text: list[str] | None = None) -> CausalGraph:
    graph = CausalGraph()
    for i in sorted(og.nodes, key=lambda n: (int(world.ev_tick[n]), n)):
        graph.add_event(
            event_id(i), ev_text[i] if ev_text else world.ev_kind[i], int(world.ev_tick[i]),
            kind=world.ev_kind[i], institution_id=INSTITUTION, embedding=world.ev_emb[i].tolist(),
        )
    for cause, effect in og.edges:
        graph.link(event_id(cause), event_id(effect))
    return graph


def deployed(world: World, link_all: bool = False) -> ObservedGraph:
    nodes = list(range(len(world.ev_kind)))
    graph = CausalGraph()
    for i in sorted(nodes, key=lambda n: (int(world.ev_tick[n]), n)):
        graph.add_event(
            event_id(i), world.ev_kind[i], int(world.ev_tick[i]), kind=world.ev_kind[i],
            institution_id=INSTITUTION, embedding=world.ev_emb[i].tolist(),
        )
        if link_all or i == world.crisis:
            graph.auto_link_predecessors(event_id(i))
    edges = [(int(c[1:]), int(e[1:])) for c, e in graph._g.edges]
    return ObservedGraph(nodes, edges, world.crisis)


def ancestors(og: ObservedGraph, max_depth: int | None = None) -> dict[int, int]:
    """Shortest backward distance from the crisis to every event that reaches it."""
    if og.crisis is None:
        return {}
    parents: dict[int, list[int]] = {}
    for cause, effect in og.edges:
        parents.setdefault(effect, []).append(cause)
    found: dict[int, int] = {}
    frontier = [og.crisis]
    depth = 0
    while frontier and (max_depth is None or depth < max_depth):
        depth += 1
        nxt = []
        for node in frontier:
            for p in parents.get(node, []):
                if p not in found and p != og.crisis:
                    found[p] = depth
                    nxt.append(p)
        frontier = nxt
    return found


def edge_quality(world: World, og: ObservedGraph) -> dict[str, float]:
    """Precision and recall of the observed ancestor set against the true causal ancestors."""
    true_anc = set(world.events_of("anc"))
    seen = set(ancestors(og))
    hit = len(true_anc & seen)
    return {
        "anc_recall": hit / len(true_anc),
        "anc_precision": hit / len(seen) if seen else float("nan"),
        "anc_found": float(len(seen)),
    }
