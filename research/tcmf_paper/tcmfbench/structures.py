"""N30: causal-graph families beyond the four-event chain.

Reviewers noted that every scenario's graph is the same shape: root -> a1 -> a2 -> crisis. This
module rewires the ancestor edges of a mixed-regime scenario into other shapes, leaving its events,
memories and query untouched. Ancestor i is event ``a{i}`` (``sc.events[i]``); ``a0``'s witness is
the gold root. ``C`` is the crisis. Edges written on the crisis topic by the on-topic leak
(``spurious``) are kept as they are.
"""
from __future__ import annotations

from dataclasses import replace

from .mixed import MixedConfig, generate_mixed
from .scenario import Scenario

# name -> (number of ancestors, edges over ancestor indices, "C" = crisis)
FAMILIES: dict[str, tuple[int, list[tuple]]] = {
    "chain3":    (2, [(0, 1), (1, "C")]),
    "chain4":    (3, [(0, 1), (1, 2), (2, "C")]),                     # the benchmark's own shape
    "chain6":    (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, "C")]),
    "diamond":   (3, [(0, 1), (0, 2), (1, "C"), (2, "C")]),
    "two_roots": (4, [(0, 1), (1, "C"), (2, 3), (3, "C")]),
    "tree":      (5, [(0, 1), (0, 2), (1, 3), (2, 4), (3, "C"), (4, "C")]),
    "side_cause": (5, [(0, 1), (1, 2), (2, 3), (3, "C"), (4, 2)]),    # a4 joins mid-chain
}


def generate_family(scenario_id: str, family: str, mcfg: MixedConfig, seed: int) -> Scenario:
    n_anc, spec = FAMILIES[family]
    sc = generate_mixed(scenario_id, replace(mcfg, chain_len=n_anc + 1), seed)
    anc = sc.events[:n_anc]
    crisis = sc.crisis_event_id

    def nid(x):
        return crisis if x == "C" else anc[x].id

    edges = [(nid(a), nid(b)) for a, b in spec]
    edges += [e for e in sc.edges if "spurious" in e[0]]
    return replace(sc, edges=edges)


def generate_many_family(n: int, family: str, mcfg: MixedConfig, base_seed: int = 0) -> list[Scenario]:
    return [generate_family(f"s{i:04d}", family, mcfg, base_seed + i) for i in range(n)]
