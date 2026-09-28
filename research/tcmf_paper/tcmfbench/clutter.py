"""N29: cluttered causal graphs - unrelated events and several false edges per graph.

Every earlier tier gives the retriever one clean chain (root -> ... -> crisis), plus at most one
fabricated edge written on the crisis surface topic. A real event log is messier: most logged
events have nothing to do with the crisis, they have their own cause-effect links among
themselves, and an automatic linker (``CausalGraph.auto_link_predecessors``) will wire some of
them into the crisis's ancestry by mistake. This module adds exactly that on top of an existing
scenario, without touching its memories:

  * ``n_background`` unrelated events, each on a topic drawn uniformly from the NON-ancestor
    topics (so the crisis surface topic is only as likely as any other one; nothing is written
    on it on purpose);
  * background cause-effect links: each earlier background event links to each later one with
    probability ``background_edge_prob``, so a false edge can pull in a whole side-history;
  * ``n_false_edges`` false edges, each from a random background event into a random node of the
    true chain (an ancestor or the crisis), so false ancestors appear at every depth and can
    change the deepest depth D that normalizes the depth weight;
  * optional ``edge_dropout`` on the true chain edges, for the combined messy setting.

The clutter uses its own RNG stream (``[seed, 29]``), so the memories, the true chain and the
query are byte-identical to the base scenario at every clutter level; each clutter level is a
paired comparison on the same memory pool.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .generator import _realize, _unit_topics
from .mixed import MixedConfig, generate_mixed
from .scenario import EventSpec, Scenario


@dataclass
class ClutterConfig:
    n_background: int = 16
    background_edge_prob: float = 0.10
    n_false_edges: int = 0
    edge_dropout: float = 0.0


def _wire(sc: Scenario, bg: list[EventSpec], ccfg: ClutterConfig, rng) -> Scenario:
    """Add background events, their links, and false edges into the true chain."""
    chain = [e.id for e in sc.events]  # root ... crisis (base scenarios carry no spurious event)
    edges = [(a, b) for a, b in sc.edges if rng.random() >= ccfg.edge_dropout]
    order = sorted(range(len(bg)), key=lambda i: bg[i].tick)
    for x in range(len(order)):
        for y in range(x + 1, len(order)):
            if rng.random() < ccfg.background_edge_prob:
                edges.append((bg[order[x]].id, bg[order[y]].id))
    for _ in range(ccfg.n_false_edges if bg else 0):
        src = bg[int(rng.integers(len(bg)))].id
        dst = chain[int(rng.integers(len(chain)))]
        if (src, dst) not in edges:
            edges.append((src, dst))
    # background first: scorers read "now" off the LAST event, which must stay the crisis
    return replace(sc, events=bg + list(sc.events), edges=edges)


def generate_clutter_mixed(scenario_id: str, mcfg: MixedConfig, ccfg: ClutterConfig,
                           seed: int) -> Scenario:
    assert mcfg.spurious_edge_rate == 0.0, "clutter replaces the single surface-topic false edge"
    return add_clutter_synthetic(generate_mixed(scenario_id, mcfg, seed), mcfg, ccfg, seed)


def add_clutter_synthetic(sc: Scenario, mcfg: MixedConfig, ccfg: ClutterConfig, seed: int) -> Scenario:
    """Clutter an existing synthetic scenario built from ``seed`` (any graph shape, N30)."""
    scenario_id = sc.scenario_id
    # Re-derive the topic geometry the base scenario used (same seed, same first draws).
    rng0 = np.random.default_rng(seed)
    topics = _unit_topics(rng0, mcfg.n_topics, mcfg.dim)
    anc_topics = {e.topic for e in sc.events[:-1]}
    free = [t for t in range(mcfg.n_topics) if t not in anc_topics]  # includes the surface topic
    rng = np.random.default_rng([seed, 29])
    bg = []
    for k in range(ccfg.n_background):
        top = int(rng.choice(free))
        bg.append(EventSpec(
            id=f"{scenario_id}_bg{k}", text=f"background event {k}",
            tick=int(rng.integers(1, mcfg.tick_span)), topic=top,
            embedding=_realize(rng, topics[top], mcfg.alpha_event),
            institution_id=sc.institution_id, kind="decision",
        ))
    return _wire(sc, bg, ccfg, rng)


def generate_many_clutter_mixed(n: int, mcfg: MixedConfig, ccfg: ClutterConfig,
                                base_seed: int = 0) -> list[Scenario]:
    return [generate_clutter_mixed(f"m{i:04d}", mcfg, ccfg, base_seed + i) for i in range(n)]


def realtext_background_texts(own_domain: str) -> list[str]:
    """Candidate background events for a real-text scenario: every other domain's logged
    decisions and crises, plus ordinary city events. None of them is on the scenario's chain."""
    from .realtext import DOMAINS, _NOISE
    out = []
    for d in DOMAINS:
        if d["name"] == own_domain:
            continue
        out += [a["event"] for a in d["ancestors"]] + list(d["crisis"])
    return out + list(_NOISE)


def add_clutter_realtext(sc: Scenario, ccfg: ClutterConfig, seed: int, embedder) -> Scenario:
    from .realtext import _fill
    rng = np.random.default_rng([seed, 29])
    pool = realtext_background_texts(sc.domain or "")
    pick = rng.permutation(len(pool))[:ccfg.n_background]
    bg = []
    for k, idx in enumerate(pick):
        txt = _fill(pool[int(idx)], rng)
        bg.append(EventSpec(
            id=f"{sc.scenario_id}_bg{k}", text=txt, tick=int(rng.integers(1, 80)), topic=-4,
            embedding=embedder.embed(txt), institution_id=sc.institution_id, kind="decision",
        ))
    embedder.flush()
    return _wire(sc, bg, ccfg, rng)
