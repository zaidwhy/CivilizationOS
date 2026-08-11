"""N16: multi-crisis scenario mode.

Two or more concurrent crises, each with its own causal chain, sharing one distractor pool,
one noise pool, and one citizen memory store - so a memory can be a true causal ancestor of
crisis A and simply irrelevant background when the query is crisis B. This is a harder test
of the causal boost's discrimination than the single-crisis benchmark: the ancestor set is no
longer the only structure in the graph, and retrieval must not let one crisis's chain leak into
another's results just because they now share a pool.

Built as ONE combined scenario (all chains' events/edges in one graph, all witnesses +
shared distractors/noise in one memory pool), materialized ONCE, then queried once per crisis
via lightweight "crisis views" that swap only the query/gold fields - so retrieval genuinely
runs against the full shared pool and shared graph, not an artificially isolated per-crisis
slice.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from .generator import _realize, _unit_topics
from .scenario import EventSpec, MemorySpec, Scenario
from . import methods as M


@dataclass
class MultiCrisisConfig:
    n_crises: int = 2
    dim: int = 64
    n_topics: int = 24
    chain_len: int = 4                 # per crisis
    n_distractors_per_crisis: int = 6  # loud symptoms for EACH crisis's own surface topic
    n_noise: int = 16                  # shared unrelated background
    witnesses_per_ancestor: int = 1
    alpha_mem: float = 0.90
    alpha_query: float = 0.90
    alpha_event: float = 0.95
    max_mem_per_citizen: int = 8
    imp_distractor: tuple[float, float] = (7.0, 9.0)
    imp_gold: tuple[float, float] = (4.0, 7.0)
    imp_noise: tuple[float, float] = (2.0, 5.0)
    tick_span: int = 80


@dataclass
class CrisisView:
    """Per-crisis query context sharing one underlying materialized memory pool and graph."""
    crisis_idx: int
    crisis_event_id: str
    query_text: str
    query_embedding: list[float]
    root_id: str
    gold_ids: set[str]
    gold_causal: set[str]
    other_crises_gold_ids: set[str]  # union of every OTHER crisis's gold witnesses - the
                                      # cross-contamination check target


def generate_multi_crisis(scenario_id: str, cfg: MultiCrisisConfig,
                          seed: int) -> tuple[Scenario, list[dict]]:
    """Returns the combined ``Scenario`` (every crisis's events/edges/memories in one graph)
    plus one ``dict`` of per-crisis generation metadata (fed to ``materialize_multi_crisis``
    after the real memory ids are assigned)."""
    rng = np.random.default_rng(seed)
    topics = _unit_topics(rng, cfg.n_topics, cfg.dim)
    inst = "inst_main"
    assert cfg.chain_len >= 2
    assert cfg.n_crises >= 2

    topic_ids = list(rng.permutation(cfg.n_topics))
    n_ancestors = cfg.chain_len - 1
    needed = cfg.n_crises * (1 + n_ancestors)  # surface + ancestors per crisis
    assert needed <= cfg.n_topics, "not enough distinct topics for this many crises/chain_len"

    all_events: list[EventSpec] = []
    all_edges: list[tuple[str, str]] = []
    all_mems: list[MemorySpec] = []
    crisis_specs: list[dict] = []

    cursor = 0
    for ci in range(cfg.n_crises):
        surface = int(topic_ids[cursor]); cursor += 1
        anc_topics = [int(t) for t in topic_ids[cursor:cursor + n_ancestors]]
        cursor += n_ancestors

        ticks = sorted(int(t) for t in rng.integers(1, cfg.tick_span, size=cfg.chain_len))
        chain_events: list[EventSpec] = []
        for i, top in enumerate(anc_topics):
            chain_events.append(EventSpec(
                id=f"{scenario_id}_c{ci}_e{i}", text=f"crisis{ci} ancestor event {i} (topic {top})",
                tick=ticks[i], topic=top, embedding=_realize(rng, topics[top], cfg.alpha_event),
                institution_id=inst, kind="decision" if i > 0 else "root_cause",
            ))
        crisis_ev = EventSpec(
            id=f"{scenario_id}_c{ci}_crisis", text=f"crisis{ci}: surface symptoms (topic {surface})",
            tick=ticks[-1], topic=surface, embedding=_realize(rng, topics[surface], cfg.alpha_event),
            institution_id=inst, kind="crisis",
        )
        chain_events.append(crisis_ev)
        chain_edges = [(chain_events[i].id, chain_events[i + 1].id)
                       for i in range(len(chain_events) - 1)]
        all_events.extend(chain_events)
        all_edges.extend(chain_edges)

        query_embedding = _realize(rng, topics[surface], cfg.alpha_query)

        gold_specs: list[MemorySpec] = []
        root_spec: MemorySpec | None = None
        for ai, ev in enumerate(chain_events[:-1]):
            label = "gold_root" if ai == 0 else "gold_chain"
            for _w in range(cfg.witnesses_per_ancestor):
                spec = MemorySpec(
                    id="", citizen_id="", text=f"witness of crisis{ci} {ev.kind} (topic {ev.topic})",
                    tick=ev.tick + int(rng.integers(0, 3)), topic=ev.topic,
                    importance=float(round(rng.uniform(*cfg.imp_gold), 1)),
                    embedding=_realize(rng, topics[ev.topic], cfg.alpha_mem), label=label,
                )
                all_mems.append(spec)
                gold_specs.append(spec)
                if ai == 0:
                    root_spec = spec

        for d in range(cfg.n_distractors_per_crisis):
            all_mems.append(MemorySpec(
                id="", citizen_id="", text=f"crisis{ci} symptom report {d} (topic {surface})",
                tick=crisis_ev.tick - int(rng.integers(0, 5)), topic=surface,
                importance=float(round(rng.uniform(*cfg.imp_distractor), 1)),
                embedding=_realize(rng, topics[surface], cfg.alpha_mem), label="distractor",
            ))

        crisis_specs.append({
            "crisis_event_id": crisis_ev.id, "query_text": crisis_ev.text,
            "query_embedding": query_embedding, "root_spec": root_spec, "gold_specs": gold_specs,
        })

    # shared background noise, topics drawn from whatever remains
    noise_pool = [int(t) for t in topic_ids[cursor:]] or [int(topic_ids[0])]
    for n in range(cfg.n_noise):
        top = int(rng.choice(noise_pool))
        all_mems.append(MemorySpec(
            id="", citizen_id="", text=f"shared background chatter {n} (topic {top})",
            tick=int(rng.integers(1, cfg.tick_span)), topic=top,
            importance=float(round(rng.uniform(*cfg.imp_noise), 1)),
            embedding=_realize(rng, topics[top], cfg.alpha_mem), label="noise",
        ))

    perm = rng.permutation(len(all_mems))
    all_mems = [all_mems[i] for i in perm]

    sc = Scenario(
        scenario_id=scenario_id, institution_id=inst, events=all_events, edges=all_edges,
        crisis_event_id=crisis_specs[0]["crisis_event_id"],
        query_text=crisis_specs[0]["query_text"], query_embedding=crisis_specs[0]["query_embedding"],
        memories=all_mems,
    )
    return sc, crisis_specs


def materialize_multi_crisis(sc: Scenario, crisis_specs: list[dict],
                             cfg: MultiCrisisConfig) -> tuple[M.Materialized, list[CrisisView]]:
    """Materialize the combined scenario once, then build one CrisisView per crisis using the
    real assigned memory ids (``spec.id`` is only filled in by ``materialize()``). Every
    witness's generated text is unique (crisis index + ancestor index + topic are all in it),
    so text is a safe join key back to the real memory id."""
    mat = M.materialize(sc, cfg.max_mem_per_citizen)

    text_to_id = {mat.mem[i]["text"]: i for i in mat.all_ids}

    per_crisis_gold: list[set[str]] = []
    per_crisis_root: list[str] = []
    for cs in crisis_specs:
        gold_ids = {text_to_id[s.text] for s in cs["gold_specs"]}
        per_crisis_gold.append(gold_ids)
        per_crisis_root.append(text_to_id[cs["root_spec"].text])

    views = []
    for ci, cs in enumerate(crisis_specs):
        others: set[str] = set()
        for cj, g in enumerate(per_crisis_gold):
            if cj != ci:
                others |= g
        views.append(CrisisView(
            crisis_idx=ci, crisis_event_id=cs["crisis_event_id"], query_text=cs["query_text"],
            query_embedding=cs["query_embedding"], root_id=per_crisis_root[ci],
            gold_ids=per_crisis_gold[ci], gold_causal=per_crisis_gold[ci],
            other_crises_gold_ids=others,
        ))
    return mat, views


def crisis_scoped_mat(mat: M.Materialized, view: CrisisView) -> M.Materialized:
    """A shallow view of ``mat`` scoped to one crisis: same shared graph, same shared memory
    pool, only the query/gold fields swapped - so ranking genuinely runs against the full
    shared pool, not an isolated slice."""
    scoped = copy.copy(mat)
    scoped.scenario = copy.copy(mat.scenario)
    scoped.scenario.crisis_event_id = view.crisis_event_id
    scoped.scenario.query_text = view.query_text
    scoped.scenario.query_embedding = view.query_embedding
    scoped.gold_ids = view.gold_ids
    scoped.gold_causal = view.gold_causal
    scoped.root_id = view.root_id
    return scoped
