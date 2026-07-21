"""Mixed-regime scenario generator: neither signal alone suffices, so fusion must win.

Two disjoint kinds of gold:

  * causal-gold  - witness memories of causal-chain ancestors, on topics DISTINCT from the
                   crisis surface (semantically far from the crisis; found only via the graph).
  * semantic-gold- genuinely relevant evidence on the crisis surface topic with HIGH alignment
                   (semantically near the crisis), whose cause is UNLOGGED (no graph event), so
                   it earns no causal boost and is found only via similarity.

Distractors sit on the surface region with LOWER alignment than semantic-gold, so similarity
can rank true semantic-gold above them. Optional ``edge_dropout`` removes causal-chain edges,
disconnecting some ancestors from the crisis (graph incompleteness) - the robustness knob.

Expected behaviour:
  semantic_rag  -> recovers semantic-gold, misses causal-gold
  causal_only   -> recovers causal-gold, misses semantic-gold
  additive TCMF -> recovers BOTH  (strictly beats either baseline)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .generator import _realize, _unit_topics
from .scenario import EventSpec, MemorySpec, Scenario


@dataclass
class MixedConfig:
    dim: int = 64
    n_topics: int = 24
    chain_len: int = 4                 # causal ancestors + crisis
    n_semantic_gold: int = 2
    n_distractors: int = 6
    n_noise: int = 8
    edge_dropout: float = 0.0          # prob each causal-chain edge is missing from the graph
    alpha_event: float = 0.95
    alpha_causal_gold: float = 0.90    # alignment to its distinct topic
    alpha_query: float = 0.90
    alpha_semantic_gold: float = 0.92  # high alignment to surface topic S -> high cos to query
    alpha_distractor: float = 0.60     # lower alignment to S -> moderate cos to query
    max_mem_per_citizen: int = 8
    imp_distractor: tuple[float, float] = (7.0, 9.0)
    imp_causal_gold: tuple[float, float] = (4.0, 7.0)
    imp_semantic_gold: tuple[float, float] = (4.0, 7.0)
    imp_noise: tuple[float, float] = (2.0, 5.0)
    tick_span: int = 80

    def total_gold(self) -> int:
        return (self.chain_len - 1) + self.n_semantic_gold


def generate_mixed(scenario_id: str, cfg: MixedConfig, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    topics = _unit_topics(rng, cfg.n_topics, cfg.dim)
    inst = "inst_main"

    tids = list(rng.permutation(cfg.n_topics))
    surface = int(tids[0])
    n_anc = cfg.chain_len - 1
    anc_topics = [int(t) for t in tids[1:1 + n_anc]]
    noise_pool = [int(t) for t in tids[1 + n_anc:]] or anc_topics

    ticks = sorted(int(t) for t in rng.integers(1, cfg.tick_span, size=cfg.chain_len))

    # causal-chain events (root ... crisis)
    events: list[EventSpec] = []
    for i, top in enumerate(anc_topics):
        events.append(EventSpec(
            id=f"{scenario_id}_e{i}", text=f"ancestor {i}", tick=ticks[i], topic=top,
            embedding=_realize(rng, topics[top], cfg.alpha_event), institution_id=inst,
            kind="root_cause" if i == 0 else "decision",
        ))
    crisis = EventSpec(
        id=f"{scenario_id}_crisis", text="crisis surface", tick=ticks[-1], topic=surface,
        embedding=_realize(rng, topics[surface], cfg.alpha_event), institution_id=inst,
        kind="crisis",
    )
    events.append(crisis)

    # chain edges with dropout (a dropped edge disconnects upstream ancestors from the crisis)
    edges: list[tuple[str, str]] = []
    for i in range(len(events) - 1):
        if rng.random() >= cfg.edge_dropout:
            edges.append((events[i].id, events[i + 1].id))

    query_embedding = _realize(rng, topics[surface], cfg.alpha_query)

    def imp(lohi):
        return float(round(rng.uniform(*lohi), 1))

    mems: list[MemorySpec] = []
    # causal-gold: one witness per ancestor
    for ai, ev in enumerate(events[:-1]):
        mems.append(MemorySpec(
            id="", citizen_id="", text=f"witness {ai}", tick=ev.tick + int(rng.integers(0, 3)),
            topic=ev.topic, importance=imp(cfg.imp_causal_gold),
            embedding=_realize(rng, topics[ev.topic], cfg.alpha_causal_gold),
            label="gold_root" if ai == 0 else "gold_chain",
        ))
    # semantic-gold: relevant, near-surface, cause unlogged (no graph event)
    for s in range(cfg.n_semantic_gold):
        mems.append(MemorySpec(
            id="", citizen_id="", text=f"relevant surface evidence {s}",
            tick=crisis.tick - int(rng.integers(0, 4)), topic=surface,
            importance=imp(cfg.imp_semantic_gold),
            embedding=_realize(rng, topics[surface], cfg.alpha_semantic_gold),
            label="gold_semantic",
        ))
    # distractors: near-surface but lower alignment, high importance
    for d in range(cfg.n_distractors):
        mems.append(MemorySpec(
            id="", citizen_id="", text=f"symptom {d}",
            tick=crisis.tick - int(rng.integers(0, 5)), topic=surface,
            importance=imp(cfg.imp_distractor),
            embedding=_realize(rng, topics[surface], cfg.alpha_distractor),
            label="distractor",
        ))
    # noise
    for n in range(cfg.n_noise):
        top = int(rng.choice(noise_pool))
        mems.append(MemorySpec(
            id="", citizen_id="", text=f"background {n}", tick=int(rng.integers(1, cfg.tick_span)),
            topic=top, importance=imp(cfg.imp_noise),
            embedding=_realize(rng, topics[top], cfg.alpha_causal_gold), label="noise",
        ))

    mems = [mems[i] for i in rng.permutation(len(mems))]

    return Scenario(
        scenario_id=scenario_id, institution_id=inst, events=events, edges=edges,
        crisis_event_id=crisis.id, query_text=crisis.text,
        query_embedding=query_embedding, memories=mems,
    )


def generate_many_mixed(n: int, cfg: MixedConfig, base_seed: int = 0) -> list[Scenario]:
    return [generate_mixed(f"m{i:04d}", cfg, base_seed + i) for i in range(n)]
