"""Tier B worlds: real text, real embeddings, and decoy causes that are present in memory.

Each scenario is one crisis with four council decisions on record. All four have a witness
memory. Exactly one led, through one mechanism event, to the crisis. ``link=True`` adds one
memory in which someone connects the mechanism to the crisis (the kind of evidence an
investigation produces); ``link=False`` is the paper's premise, where nothing in memory that
concerns the cause mentions the crisis.

A scenario is expressed as the same ``World`` the synthetic tier uses, so every retriever and
graph builder runs on it unchanged.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .graphs import ObservedGraph
from .world import World, WorldConfig

INCIDENTS = json.loads((Path(__file__).parent / "incidents.json").read_text(encoding="utf-8"))
N_NOISE = 20
REPLICATES = 4
# Event index layout, matching the synthetic tier (ancestor d sits at index d-1).
MECHANISM, ROOT, CRISIS = 0, 1, 5


@dataclass
class TextWorld:
    world: World
    scenario_id: str
    domain: str
    cluster: str               # domain + true cause: the unit of independent text
    crisis_text: str
    mem_text: list[str]
    ev_text: list[str]
    options: list[str]         # shuffled
    answer: int                # index into options
    decoy_mechanism: dict[int, str]   # decoy event index -> the mechanism that decision would have had


def scenario_specs() -> list[tuple[int, int, int]]:
    """(domain index, true cause index, replicate) for the full 8 x 4 x 4 design."""
    return [(d, c, r) for d in range(len(INCIDENTS["domains"])) for c in range(4) for r in range(REPLICATES)]


def all_texts() -> list[str]:
    texts = list(INCIDENTS["noise"])
    for dom in INCIDENTS["domains"]:
        texts += [dom["crisis"], *dom["symptoms"]]
        for cause in dom["causes"]:
            texts += [cause[k] for k in ("decision", "witness", "mechanism", "mech_witness", "link")]
    return texts


def build(spec: tuple[int, int, int], link: bool, embed: dict[str, np.ndarray]) -> TextWorld:
    d, true_cause, rep = spec
    dom = INCIDENTS["domains"][d]
    rng = np.random.default_rng([d, true_cause, rep])
    causes = dom["causes"]
    decoys = [i for i in range(4) if i != true_cause]
    now, crisis_tick = 200, 199

    root_tick = int(rng.integers(50, 141))
    mech_tick = int(rng.integers(root_tick + 5, 190))
    ev_text = [causes[true_cause]["mechanism"], causes[true_cause]["decision"]]
    ev_tick = [mech_tick, root_tick]
    ev_kind = ["anc1", "anc2"]
    for i in decoys:
        ev_text.append(causes[i]["decision"])
        ev_tick.append(int(rng.integers(50, 191)))
        ev_kind.append("decoy")
    ev_text.append(dom["crisis"])
    ev_tick.append(crisis_tick)
    ev_kind.append("crisis")

    mem: list[tuple[str, int, tuple[float, float], str]] = [
        (causes[true_cause]["witness"], root_tick + int(rng.integers(0, 3)), (4, 7), "anc2"),
        (causes[true_cause]["mech_witness"], mech_tick + int(rng.integers(0, 3)), (4, 7), "anc1"),
    ]
    if link:
        mem.append((causes[true_cause]["link"], crisis_tick - int(rng.integers(1, 4)), (4, 7), "anc_link"))
    for slot, i in enumerate(decoys):
        mem.append((causes[i]["witness"], ev_tick[2 + slot] + int(rng.integers(0, 3)), (4, 7), "decoy"))
    for text in dom["symptoms"]:
        mem.append((text, crisis_tick - int(rng.integers(0, 5)), (7, 9), "symptom"))
    for j in rng.choice(len(INCIDENTS["noise"]), size=N_NOISE, replace=False):
        mem.append((INCIDENTS["noise"][int(j)], int(rng.integers(1, crisis_tick)), (2, 5), "noise"))
    imp = [round(float(rng.uniform(*m[2])), 1) for m in mem]
    order = [int(i) for i in rng.permutation(len(mem))]

    option_order = [int(i) for i in rng.permutation(4)]
    world = World(
        cfg=WorldConfig(dim=len(embed[dom["crisis"]]), depth=2, n_decoy_events=3,
                        n_symptoms=len(dom["symptoms"]), n_noise=N_NOISE, now=now),
        query=embed[dom["crisis"]],
        mem_emb=np.asarray([embed[mem[i][0]] for i in order]),
        mem_tick=np.asarray([mem[i][1] for i in order]),
        mem_imp=np.asarray([imp[i] for i in order]),
        mem_label=[mem[i][3] for i in order],
        ev_emb=np.asarray([embed[t] for t in ev_text]),
        ev_tick=np.asarray(ev_tick),
        ev_kind=ev_kind,
        true_edges=[(ROOT, MECHANISM), (MECHANISM, CRISIS)],
        crisis=CRISIS,
    )
    return TextWorld(
        world=world,
        scenario_id=f"{dom['id']}-c{true_cause}-r{rep}",
        domain=dom["id"],
        cluster=f"{dom['id']}-c{true_cause}",
        crisis_text=dom["crisis"],
        mem_text=[mem[i][0] for i in order],
        ev_text=ev_text,
        options=[causes[i]["option"] for i in option_order],
        answer=option_order.index(true_cause),
        decoy_mechanism={2 + slot: causes[i]["mechanism"] for slot, i in enumerate(decoys)},
    )


def wrong_root(tw: TextWorld, rng: np.random.Generator,
               embed: dict[str, np.ndarray]) -> tuple[World, list[str], ObservedGraph]:
    """A graph that is wrong from end to end: it names one of the unrelated decisions as the
    root cause and that decision's own would-be mechanism as the middle step. Returns the
    world as that graph describes it (event text and embeddings), and the graph."""
    impostor = int(rng.choice(tw.world.events_of("decoy")))
    mechanism = tw.decoy_mechanism[impostor]
    ev_text = list(tw.ev_text)
    ev_text[MECHANISM] = mechanism
    ev_emb = tw.world.ev_emb.copy()
    ev_emb[MECHANISM] = embed[mechanism]
    graph = ObservedGraph(list(range(len(ev_text))), [(impostor, MECHANISM), (MECHANISM, CRISIS)], CRISIS)
    return replace(tw.world, ev_emb=ev_emb), ev_text, graph
