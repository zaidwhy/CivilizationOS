"""Scenario generator whose ground truth does not depend on the graph a retriever is given.

A world has a latent causal chain ``root = anc[depth] -> ... -> anc[1] -> crisis`` and a set
of decoy events: earlier events of the same institution that caused nothing. Gold is defined
by the latent chain. What a retriever sees is an ``ObservedGraph`` built separately
(``graphs.py``), which may be perfect, noisy, wrong, or the output of the deployed linker.

Geometry is exact rather than approximate: topics come from an orthonormal basis, so the three
similarity knobs mean what they say.

  rho        cosine between an ancestor's topic and the crisis topic. 0 is the paper's premise
             ("the cause looks nothing like the crisis").
  rho_decoy  the same for decoy events.
  beta       how much a witness memory of an event also mentions that event's effect. 0 is the
             paper's premise (a cause memory carries no trace of what it led to).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

NOISE_TOPICS = 8


@dataclass(frozen=True)
class WorldConfig:
    dim: int = 64
    depth: int = 3
    n_decoy_events: int = 6
    n_symptoms: int = 6
    n_noise: int = 20
    rho: float = 0.0
    rho_decoy: float = 0.0
    beta: float = 0.0
    alpha_mem: float = 0.90
    alpha_event: float = 0.95
    alpha_query: float = 0.90
    root_age: tuple[int, int] = (60, 150)
    decoy_age: tuple[int, int] = (1, 150)
    now: int = 200


@dataclass
class World:
    cfg: WorldConfig
    query: np.ndarray                 # (dim,)
    mem_emb: np.ndarray               # (N, dim)
    mem_tick: np.ndarray              # (N,)
    mem_imp: np.ndarray               # (N,)
    mem_label: list[str]              # "anc1".."ancD" | "decoy" | "symptom" | "noise"
    ev_emb: np.ndarray                # (E, dim)
    ev_tick: np.ndarray               # (E,)
    ev_kind: list[str]                # "anc1".."ancD" | "decoy" | "crisis"
    true_edges: list[tuple[int, int]]  # (cause event index, effect event index)
    crisis: int

    @property
    def n(self) -> int:
        return len(self.mem_label)

    def labelled(self, *labels: str) -> set[int]:
        return {i for i, lab in enumerate(self.mem_label) if lab in labels}

    @property
    def causal_gold(self) -> set[int]:
        return {i for i, lab in enumerate(self.mem_label) if lab.startswith("anc")}

    @property
    def root_gold(self) -> set[int]:
        return self.labelled(f"anc{self.cfg.depth}")

    @property
    def symptom_gold(self) -> set[int]:
        return self.labelled("symptom")

    def events_of(self, kind_prefix: str) -> list[int]:
        return [i for i, k in enumerate(self.ev_kind) if k.startswith(kind_prefix)]


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _realize(rng: np.random.Generator, topic: np.ndarray, alpha: float) -> np.ndarray:
    noise = _unit(rng.standard_normal(topic.shape[0]))
    return _unit(alpha * topic + np.sqrt(1.0 - alpha * alpha) * noise)


def generate(cfg: WorldConfig, seed: int) -> World:
    n_topics = 1 + cfg.depth + cfg.n_decoy_events + NOISE_TOPICS
    if n_topics > cfg.dim:
        raise ValueError(f"need {n_topics} orthogonal topics but dim is {cfg.dim}")
    rng = np.random.default_rng(seed)
    basis, _ = np.linalg.qr(rng.standard_normal((cfg.dim, cfg.dim)))
    basis = basis.T
    surface = basis[0]

    def tilted(base: np.ndarray, rho: float) -> np.ndarray:
        return _unit(rho * surface + np.sqrt(1.0 - rho * rho) * base)

    anc_topic = {d: tilted(basis[d], cfg.rho) for d in range(1, cfg.depth + 1)}
    decoy_topic = [tilted(basis[1 + cfg.depth + j], cfg.rho_decoy) for j in range(cfg.n_decoy_events)]
    noise_topic = basis[1 + cfg.depth + cfg.n_decoy_events:][:NOISE_TOPICS]

    crisis_tick = cfg.now - 1
    root_tick = crisis_tick - int(rng.integers(cfg.root_age[0], cfg.root_age[1] + 1))
    between = sorted(int(t) for t in rng.integers(root_tick + 1, crisis_tick, size=cfg.depth - 1))
    anc_tick = {cfg.depth: root_tick}
    for d, t in zip(range(cfg.depth - 1, 0, -1), between):
        anc_tick[d] = t

    ev_emb, ev_tick, ev_kind = [], [], []
    for d in range(1, cfg.depth + 1):
        ev_emb.append(_realize(rng, anc_topic[d], cfg.alpha_event))
        ev_tick.append(anc_tick[d])
        ev_kind.append(f"anc{d}")
    for j in range(cfg.n_decoy_events):
        ev_emb.append(_realize(rng, decoy_topic[j], cfg.alpha_event))
        ev_tick.append(crisis_tick - int(rng.integers(cfg.decoy_age[0], cfg.decoy_age[1] + 1)))
        ev_kind.append("decoy")
    crisis = len(ev_kind)
    ev_emb.append(_realize(rng, surface, cfg.alpha_event))
    ev_tick.append(crisis_tick)
    ev_kind.append("crisis")
    # anc d sits at event index d-1; its effect is anc d-1, or the crisis for d == 1.
    true_edges = [(d - 1, d - 2 if d > 1 else crisis) for d in range(cfg.depth, 0, -1)]

    emb, tick, imp, label = [], [], [], []

    def add(vec: np.ndarray, t: int, importance: tuple[float, float], lab: str) -> None:
        emb.append(vec)
        tick.append(max(1, t))
        imp.append(round(float(rng.uniform(*importance)), 1))
        label.append(lab)

    for d in range(1, cfg.depth + 1):
        effect_topic = anc_topic[d - 1] if d > 1 else surface
        base = _unit((1.0 - cfg.beta) * anc_topic[d] + cfg.beta * effect_topic)
        add(_realize(rng, base, cfg.alpha_mem), anc_tick[d] + int(rng.integers(0, 3)), (4, 7), f"anc{d}")
    for j in range(cfg.n_decoy_events):
        add(_realize(rng, decoy_topic[j], cfg.alpha_mem),
            ev_tick[cfg.depth + j] + int(rng.integers(0, 3)), (4, 7), "decoy")
    for _ in range(cfg.n_symptoms):
        add(_realize(rng, surface, cfg.alpha_mem), crisis_tick - int(rng.integers(0, 5)), (7, 9), "symptom")
    for _ in range(cfg.n_noise):
        topic = noise_topic[int(rng.integers(0, len(noise_topic)))]
        add(_realize(rng, topic, cfg.alpha_mem), int(rng.integers(1, crisis_tick)), (2, 5), "noise")

    order = rng.permutation(len(label))
    return World(
        cfg=cfg,
        query=_realize(rng, surface, cfg.alpha_query),
        mem_emb=np.asarray(emb)[order],
        mem_tick=np.asarray(tick)[order],
        mem_imp=np.asarray(imp)[order],
        mem_label=[label[i] for i in order],
        ev_emb=np.asarray(ev_emb),
        ev_tick=np.asarray(ev_tick),
        ev_kind=ev_kind,
        true_edges=true_edges,
        crisis=crisis,
    )
