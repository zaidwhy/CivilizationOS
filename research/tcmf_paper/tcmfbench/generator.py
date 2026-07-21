"""Synthetic scenario generator with controlled semantics and known causal ground truth.

Design goal: create the phenomenon the paper is about - *causal relevance is not semantic
similarity*. We build an embedding space where:

  * the crisis "surface" topic S is what the crisis sounds like (symptoms);
  * the root-cause topic C is a DIFFERENT topic, so root-cause memories are semantically FAR
    from the crisis but causally central;
  * distractor memories share topic S (semantically near the crisis, causally irrelevant) and
    are given high importance - the "loud symptom" that fools semantic + episodic retrieval.

Embeddings: each topic is a near-orthogonal unit vector in R^dim. A memory / event on topic t
is ``normalize(alpha * topic[t] + sqrt(1-alpha^2) * unit_noise)``. Two independent
realizations of the same topic then have expected cosine ~ alpha^2, and realizations of
different (near-orthogonal) topics have cosine ~ alpha^2 * <topic_i, topic_j> ~ 0. So ``alpha``
directly sets within-topic similarity, independent of ``dim`` (unlike additive Gaussian noise,
whose magnitude grows with sqrt(dim) and washes the signal out). Everything is seeded and
deterministic; no LLM or network is used, so the benchmark is fully reproducible offline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .scenario import EventSpec, MemorySpec, Scenario


@dataclass
class GenConfig:
    dim: int = 64
    n_topics: int = 24            # pool of distinct topics to draw from
    chain_len: int = 4            # causal-chain length incl. crisis node (>=2)
    n_distractors: int = 6        # loud symptom memories (topic S, high importance)
    n_noise: int = 8              # unrelated background memories
    witnesses_per_ancestor: int = 1
    # alpha = alignment to topic; within-topic cosine ~ alpha^2, cross-topic ~ 0.
    alpha_mem: float = 0.90       # memory embedding alignment to its topic
    alpha_query: float = 0.90     # crisis query alignment to surface topic
    alpha_event: float = 0.95     # graph event alignment to its topic (tighter)
    max_mem_per_citizen: int = 8  # keep <= retriever's per-citizen top-k to avoid pruning loss
    imp_distractor: tuple[float, float] = (7.0, 9.0)
    imp_gold: tuple[float, float] = (4.0, 7.0)
    imp_noise: tuple[float, float] = (2.0, 5.0)
    tick_span: int = 80


def _unit_topics(rng: np.random.Generator, n: int, dim: int) -> np.ndarray:
    v = rng.standard_normal((n, dim))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def _realize(rng: np.random.Generator, topic_vec: np.ndarray, alpha: float) -> list[float]:
    """Angle-mix the topic with an independent unit-noise direction; within-topic
    cosine ~ alpha^2, independent of dimension."""
    noise = rng.standard_normal(topic_vec.shape[0])
    noise /= np.linalg.norm(noise) or 1.0
    v = alpha * topic_vec + math.sqrt(max(0.0, 1.0 - alpha * alpha)) * noise
    v = v / (np.linalg.norm(v) or 1.0)
    return v.astype(np.float32).tolist()


def generate(scenario_id: str, cfg: GenConfig, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    topics = _unit_topics(rng, cfg.n_topics, cfg.dim)

    inst = "inst_main"
    assert cfg.chain_len >= 2, "chain_len must include root ... crisis (>=2)"

    # --- pick topics: surface S (crisis), and one distinct topic per chain ancestor ---
    topic_ids = list(rng.permutation(cfg.n_topics))
    surface = int(topic_ids[0])                      # crisis surface topic S
    n_ancestors = cfg.chain_len - 1
    ancestor_topics = [int(t) for t in topic_ids[1 : 1 + n_ancestors]]  # distinct from S
    noise_topic_pool = [int(t) for t in topic_ids[1 + n_ancestors :]] or ancestor_topics

    # --- build the causal chain events: root (earliest) ... crisis (latest) ---
    ticks = sorted(int(t) for t in rng.integers(1, cfg.tick_span, size=cfg.chain_len))
    events: list[EventSpec] = []
    # ancestors first (root-cause is index 0), crisis last
    for i, top in enumerate(ancestor_topics):
        events.append(
            EventSpec(
                id=f"{scenario_id}_e{i}",
                text=f"ancestor event {i} (topic {top})",
                tick=ticks[i],
                topic=top,
                embedding=_realize(rng, topics[top], cfg.alpha_event),
                institution_id=inst,
                kind="decision" if i > 0 else "root_cause",
            )
        )
    crisis = EventSpec(
        id=f"{scenario_id}_crisis",
        text=f"crisis: surface symptoms (topic {surface})",
        tick=ticks[-1],
        topic=surface,
        embedding=_realize(rng, topics[surface], cfg.alpha_event),
        institution_id=inst,
        kind="crisis",
    )
    events.append(crisis)

    # chain edges: root -> a1 -> ... -> crisis
    edges = [(events[i].id, events[i + 1].id) for i in range(len(events) - 1)]

    # --- query embedding: a fresh realization on the surface topic ---
    query_embedding = _realize(rng, topics[surface], cfg.alpha_query)

    # --- memories ---
    mems: list[MemorySpec] = []

    def imp(rng_, lo_hi):
        return float(round(rng_.uniform(*lo_hi), 1))

    # witness memories for each causal ancestor (gold). Root cause is events[0].
    for ai, ev in enumerate(events[:-1]):  # exclude the crisis node itself
        label = "gold_root" if ai == 0 else "gold_chain"
        for w in range(cfg.witnesses_per_ancestor):
            mems.append(
                MemorySpec(
                    id="",
                    citizen_id="",
                    text=f"witness of {ev.kind} (topic {ev.topic})",
                    tick=ev.tick + int(rng.integers(0, 3)),
                    topic=ev.topic,
                    importance=imp(rng, cfg.imp_gold),
                    embedding=_realize(rng, topics[ev.topic], cfg.alpha_mem),
                    label=label,
                )
            )
    # distractors: loud symptoms on the surface topic, high importance
    for d in range(cfg.n_distractors):
        mems.append(
            MemorySpec(
                id="", citizen_id="",
                text=f"symptom report {d} (topic {surface})",
                tick=crisis.tick - int(rng.integers(0, 5)),
                topic=surface,
                importance=imp(rng, cfg.imp_distractor),
                embedding=_realize(rng, topics[surface], cfg.alpha_mem),
                label="distractor",
            )
        )
    # noise: unrelated background
    for n in range(cfg.n_noise):
        top = int(rng.choice(noise_topic_pool))
        mems.append(
            MemorySpec(
                id="", citizen_id="",
                text=f"background chatter {n} (topic {top})",
                tick=int(rng.integers(1, cfg.tick_span)),
                topic=top,
                importance=imp(rng, cfg.imp_noise),
                embedding=_realize(rng, topics[top], cfg.alpha_mem),
                label="noise",
            )
        )

    # shuffle memory order so nothing leaks through insertion order
    perm = rng.permutation(len(mems))
    mems = [mems[i] for i in perm]

    return Scenario(
        scenario_id=scenario_id,
        institution_id=inst,
        events=events,
        edges=edges,
        crisis_event_id=crisis.id,
        query_text=crisis.text,
        query_embedding=query_embedding,
        memories=mems,
    )


def generate_many(n: int, cfg: GenConfig, base_seed: int = 0) -> list[Scenario]:
    return [generate(f"s{i:04d}", cfg, base_seed + i) for i in range(n)]
