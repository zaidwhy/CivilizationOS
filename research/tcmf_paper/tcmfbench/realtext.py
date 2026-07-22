"""Real-text tier: natural-language scenarios embedded with a real encoder (Ollama
nomic-embed-text), to check that the synthetic-tier findings survive real embedding geometry.

Ground truth is still by construction (labels), independent of the embeddings:
  * causal-gold  - first-person witness memories phrased in the ROOT-CAUSE / governance
                   vocabulary (semantically far from the crisis symptoms, near their ancestor
                   event); found via the causal graph.
  * semantic-gold- relevant evidence phrased in the CRISIS-symptom vocabulary whose cause is
                   unlogged (no graph event); found via similarity.
  * distractor   - loud symptom reports (crisis vocabulary, high importance, causally irrelevant).
  * noise        - unrelated city life.

Whether causal-gold really lands far from the crisis and near its ancestor is now decided by
the encoder, not by us - that is exactly what this tier tests.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .embed_client import EmbedClient
from .scenario import EventSpec, MemorySpec, Scenario

# Each domain: a crisis surface, an ordered causal chain (root cause first) of (event, witness)
# pairs, semantically-relevant-but-unlogged evidence, and loud symptom distractors.
DOMAINS: list[dict] = [
    {
        "name": "plague",
        "crisis": [
            "A plague is tearing through the {district} market district; the clinics are overrun.",
            "An outbreak of hemorrhagic fever has hit {district}; patients are dying faster than we can treat them.",
        ],
        "ancestors": [
            {"event": "The Senate voted down emergency quarantine funding for {district} two months ago.",
             "witness": "I sat in the chamber when they killed the quarantine budget - the treasury bloc refused to release a single coin."},
            {"event": "With no budget, the public-health inspectorate laid off half its field staff.",
             "witness": "Our inspection team was gutted after the funding vote; we stopped doing ward checks entirely."},
            {"event": "Sanitation contracts for the market wards were cancelled to save money.",
             "witness": "The waste-hauling contract for the market was torn up last quarter; the drains have been backing up since."},
        ],
        "semantic_gold": [
            "Three more families on {street} came down with the fever this morning; two children are critical.",
            "The clinic on {street} has run out of beds; the sick are lying in the corridors.",
        ],
        "distractor": [
            "The whole market reeks of sickness and everyone is coughing.",
            "People keep collapsing near the central fountain; it is terrifying.",
            "The apothecary sold out of every remedy by noon.",
            "Funeral carts have been rolling through {district} all day.",
        ],
    },
    {
        "name": "water",
        "crisis": [
            "The taps in {district} have run dry and residents are rioting over water.",
            "A severe water shortage has gripped {district}; fights are breaking out at the wells.",
        ],
        "ancestors": [
            {"event": "The council quietly approved diverting the {district} reservoir to the industrial canal.",
             "witness": "I saw the diversion order signed - they rerouted our reservoir to the factory canal without telling anyone."},
            {"event": "Maintenance on the aqueduct was deferred for three years to cut costs.",
             "witness": "We flagged the cracked aqueduct spans for years; every repair request was denied for budget reasons."},
            {"event": "The backup pumping station was decommissioned and its parts sold.",
             "witness": "They stripped and sold the old backup pumps last winter; there is no fallback supply now."},
        ],
        "semantic_gold": [
            "The queue at the {street} well stretches for two blocks and tempers are boiling.",
            "Families on {street} have had no running water for four days straight.",
        ],
        "distractor": [
            "Everyone is desperate and thirsty; the heat makes it unbearable.",
            "People are hauling buckets from the river, which is filthy.",
            "The price of a jug of water has tripled overnight.",
            "Children are crying at the dry public fountains.",
        ],
    },
    {
        "name": "cyber",
        "crisis": [
            "The city's payment and records systems are frozen; nothing works in {district}.",
            "A cyberattack has crippled municipal services across {district}; screens are dark everywhere.",
        ],
        "ancestors": [
            {"event": "The IT modernization budget was slashed and security patching was suspended.",
             "witness": "I run the systems desk - after the budget cut we were ordered to stop applying security patches."},
            {"event": "A no-bid contract handed the network to an unvetted outside vendor.",
             "witness": "The council gave our whole network to some unvetted vendor on a no-bid deal; they had the master keys."},
            {"event": "Staff warnings about exposed admin access were ignored for a year.",
             "witness": "We filed warning after warning about the open admin ports; management shelved every one of them."},
        ],
        "semantic_gold": [
            "The clerks on {street} cannot process a single payment; the terminals are all locked.",
            "Residents queued at the {street} office are being turned away because the records are inaccessible.",
        ],
        "distractor": [
            "Every screen in the building is showing an error and nobody can log in.",
            "The card readers are dead so it is cash only, and no one carries cash.",
            "Phones are ringing off the hook with panicked residents.",
            "The office is chaos; people are shouting at the frozen counters.",
        ],
    },
    {
        "name": "crime",
        "crisis": [
            "A crime wave has engulfed {district}; break-ins and assaults every night.",
            "Violence is surging across {district}; residents are afraid to leave their homes.",
        ],
        "ancestors": [
            {"event": "The precinct's patrol budget was cut and two beats were eliminated.",
             "witness": "After the budget cut they axed two of our patrol beats; whole blocks go uncovered at night now."},
            {"event": "The youth employment program that kept the district busy was defunded.",
             "witness": "They defunded the youth work program I ran; hundreds of kids were left with nothing overnight."},
            {"event": "Street lighting repairs were postponed indefinitely across the ward.",
             "witness": "Every broken streetlight ticket I filed got postponed; half the ward is pitch dark after dusk."},
        ],
        "semantic_gold": [
            "There were three more break-ins on {street} last night; shopkeepers are terrified.",
            "A resident on {street} was mugged at knifepoint just steps from her door.",
        ],
        "distractor": [
            "You can feel the fear in the streets; nobody goes out after dark.",
            "Shop windows are smashed all along the main road.",
            "People are buying locks and bars faster than the stores can stock them.",
            "The sound of sirens never seems to stop anymore.",
        ],
    },
    {
        "name": "housing",
        "crisis": [
            "An eviction crisis has erupted in {district}; families are being put on the street.",
            "Mass evictions are sweeping {district}; the shelters are already full.",
        ],
        "ancestors": [
            {"event": "The council rezoned {district} for luxury development after a closed-door deal.",
             "witness": "I have the minutes from the closed session where they rezoned us for luxury towers; a developer was in the room."},
            {"event": "Rent-stabilization protections were quietly repealed last spring.",
             "witness": "They repealed the rent caps in a spring omnibus bill; nobody announced it and rents doubled."},
            {"event": "The emergency housing fund was redirected to the development subsidy.",
             "witness": "Our emergency housing fund got swept into a developer subsidy line; there is no relief money left."},
        ],
        "semantic_gold": [
            "Four more families on {street} got eviction notices this week.",
            "The building on {street} emptied overnight; belongings are piled on the curb.",
        ],
        "distractor": [
            "There are mattresses and boxes on every sidewalk in the district.",
            "The shelter turned away dozens of people last night for lack of space.",
            "Landlords are posting notices on doors up and down the block.",
            "You see families sleeping in the park now, which never used to happen.",
        ],
    },
    {
        "name": "power",
        "crisis": [
            "The power grid has failed across {district}; the whole quarter is dark and cold.",
            "A cascading blackout has hit {district}; hospitals are running on fumes.",
        ],
        "ancestors": [
            {"event": "The utility's maintenance fund was diverted to shareholder payouts.",
             "witness": "I was on the utility board when they drained the maintenance fund into a shareholder dividend."},
            {"event": "Grid inspectors flagged the failing substation but repairs were denied.",
             "witness": "We red-tagged that substation twice; every repair authorization got denied to protect the margin."},
            {"event": "The backup generators were sold off during the last cost-cutting round.",
             "witness": "They sold our backup generators in the last cost-cutting round; there is nothing to fall back on."},
        ],
        "semantic_gold": [
            "The homes on {street} have been without power for eighteen hours now.",
            "The clinic on {street} is running its last generator and the fuel is almost gone.",
        ],
        "distractor": [
            "Every building on the block is pitch black and freezing.",
            "People are lighting candles and hoping the fire does not spread.",
            "The traffic signals are all dead and the intersections are chaos.",
            "Food is spoiling in every icebox in the district.",
        ],
    },
]

_DISTRICTS = ["North", "South", "East", "West", "Old Town", "Riverside", "Harbor", "Highgate"]
_STREETS = ["Mill", "Canal", "Ash", "Foundry", "Market", "Cobb", "Larch", "Quarry"]
_NOISE = [
    "The bakery on the corner has a new sourdough that everyone is talking about.",
    "The ferry schedule changed again and the commuters are grumbling.",
    "A street musician drew a big crowd in the plaza this afternoon.",
    "The football club won its match and the taverns were packed.",
    "They repainted the old library facade a cheerful shade of blue.",
    "The weekend flea market added a whole row of antique stalls.",
    "A pair of swans nested by the boathouse and the children love them.",
    "The tailor is running a sale on winter coats this week.",
    "The community garden's tomatoes came in early this year.",
    "A new coffee cart opened by the university gates.",
    "The clock tower was finally repaired and chimes on the hour again.",
    "The harbor festival fireworks are scheduled for next Friday.",
]


@dataclass
class RealConfig:
    n_semantic_gold: int = 2
    n_distractors: int = 5
    n_noise: int = 6
    edge_dropout: float = 0.0
    max_mem_per_citizen: int = 8
    imp_distractor: tuple[float, float] = (7.0, 9.0)
    imp_causal_gold: tuple[float, float] = (4.0, 7.0)
    imp_semantic_gold: tuple[float, float] = (4.0, 7.0)
    imp_noise: tuple[float, float] = (2.0, 5.0)
    tick_span: int = 80

    def total_gold(self, n_ancestors: int) -> int:
        return n_ancestors + self.n_semantic_gold


def _fill(text: str, rng) -> str:
    return text.replace("{district}", rng.choice(_DISTRICTS)).replace("{street}", rng.choice(_STREETS))


def generate_realtext(scenario_id: str, cfg: RealConfig, seed: int,
                      embedder: EmbedClient) -> Scenario:
    rng = np.random.default_rng(seed)
    dom = DOMAINS[int(rng.integers(len(DOMAINS)))]
    inst = "inst_main"
    ancestors = dom["ancestors"]
    n_anc = len(ancestors)
    chain_len = n_anc + 1
    ticks = sorted(int(t) for t in rng.integers(1, cfg.tick_span, size=chain_len))

    def emb(text):
        return embedder.embed(text)

    # events: root-cause first ... crisis last
    events: list[EventSpec] = []
    for i, anc in enumerate(ancestors):
        txt = _fill(anc["event"], rng)
        events.append(EventSpec(
            id=f"{scenario_id}_e{i}", text=txt, tick=ticks[i], topic=i,
            embedding=emb(txt), institution_id=inst,
            kind="root_cause" if i == 0 else "decision",
        ))
    crisis_txt = _fill(rng.choice(dom["crisis"]), rng)
    crisis = EventSpec(
        id=f"{scenario_id}_crisis", text=crisis_txt, tick=ticks[-1], topic=-1,
        embedding=emb(crisis_txt), institution_id=inst, kind="crisis",
    )
    events.append(crisis)

    edges = [(events[i].id, events[i + 1].id) for i in range(len(events) - 1)
             if rng.random() >= cfg.edge_dropout]

    query_embedding = emb(crisis_txt)

    def imp(lohi):
        return float(round(rng.uniform(*lohi), 1))

    mems: list[MemorySpec] = []
    # causal-gold witnesses (one per ancestor)
    for ai, anc in enumerate(ancestors):
        txt = _fill(anc["witness"], rng)
        mems.append(MemorySpec(
            id="", citizen_id="", text=txt, tick=events[ai].tick + int(rng.integers(0, 3)),
            topic=ai, importance=imp(cfg.imp_causal_gold), embedding=emb(txt),
            label="gold_root" if ai == 0 else "gold_chain",
        ))
    # semantic-gold (crisis vocabulary, cause unlogged)
    sg = list(rng.permutation(len(dom["semantic_gold"])))[:cfg.n_semantic_gold]
    for s in sg:
        txt = _fill(dom["semantic_gold"][s], rng)
        mems.append(MemorySpec(
            id="", citizen_id="", text=txt, tick=crisis.tick - int(rng.integers(0, 4)),
            topic=-1, importance=imp(cfg.imp_semantic_gold), embedding=emb(txt),
            label="gold_semantic",
        ))
    # distractors (symptom vocabulary, high importance)
    for _ in range(cfg.n_distractors):
        txt = _fill(dom["distractor"][int(rng.integers(len(dom["distractor"])))], rng)
        mems.append(MemorySpec(
            id="", citizen_id="", text=txt, tick=crisis.tick - int(rng.integers(0, 5)),
            topic=-2, importance=imp(cfg.imp_distractor), embedding=emb(txt), label="distractor",
        ))
    # noise (unrelated)
    for _ in range(cfg.n_noise):
        txt = _NOISE[int(rng.integers(len(_NOISE)))]
        mems.append(MemorySpec(
            id="", citizen_id="", text=txt, tick=int(rng.integers(1, cfg.tick_span)),
            topic=-3, importance=imp(cfg.imp_noise), embedding=emb(txt), label="noise",
        ))

    mems = [mems[i] for i in rng.permutation(len(mems))]
    embedder.flush()

    return Scenario(
        scenario_id=scenario_id, institution_id=inst, events=events, edges=edges,
        crisis_event_id=crisis.id, query_text=crisis_txt,
        query_embedding=query_embedding, memories=mems,
        domain=dom["name"],
    )


def generate_many_realtext(n: int, cfg: RealConfig, embedder: EmbedClient,
                           base_seed: int = 0) -> list[Scenario]:
    return [generate_realtext(f"r{i:04d}", cfg, base_seed + i, embedder) for i in range(n)]
