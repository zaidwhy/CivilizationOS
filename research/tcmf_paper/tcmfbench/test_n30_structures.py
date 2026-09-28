"""N30 tests: graph families beyond the four-event chain, and the leaked-pair map.

Run: python -m pytest tcmfbench/test_n30_structures.py
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .mixed import MixedConfig
from .structures import FAMILIES, generate_family

ROOT = Path(__file__).resolve().parents[1]


def _r():
    return json.load(open(ROOT / "results_structures_n30" / "results_structures_n30.json"))


def test_families_rewire_only_edges_and_reach_every_ancestor():
    mc = MixedConfig(n_distractors=20, n_noise=55)
    for fam, (n_anc, spec) in FAMILIES.items():
        sc = generate_family("s0", fam, mc, 11)
        assert sc.events[-1].id == sc.crisis_event_id
        assert len(sc.edges) == len(spec)
        mat = M.materialize(sc, mc.max_mem_per_citizen)
        anc = M._ancestor_map(mat, clean=True, max_depth=8)
        assert {e.id for e in sc.events[:n_anc]} == set(anc), fam


def test_clean_graphs_operators_match_where_additive_weight_clears_its_bound():
    f = _r()["families"]
    for fam in FAMILIES:
        for tag in ("prox", "root"):
            v = f[f"{fam}_clean_{tag}"]
            if v["frac_add4_suffices"] >= 0.95:
                assert abs(v["add_l4"] - v["mult_l16"]) < 0.015, (fam, tag)  # chain6 root: 0.011
            else:  # long chains, proximate weights: lambda=4 sits below the additive bound
                assert fam in ("chain6", "side_cause") and tag == "prox" and v["mult_l16"] > v["add_l4"]


def test_on_topic_leak_favours_addition_in_every_family():
    f = _r()["families"]
    for fam in FAMILIES:
        v = f[f"{fam}_onleak_prox"]
        assert v["add_l4"] - v["best_mult"] > 0.1, fam
        r = f[f"{fam}_onleak_root"]
        assert r["add_l4"] >= r["best_mult"] - 0.002, fam


def test_false_edges_hurt_every_family_and_root_weights_favour_multiplication():
    f = _r()["families"]
    for fam in FAMILIES:
        for tag in ("prox", "root"):
            assert f[f"{fam}_clean_{tag}"]["add_l4"] - f[f"{fam}_clutter_{tag}"]["add_l4"] > 0.2, (fam, tag)
        assert f[f"{fam}_clutter_root"]["mult_l16"] > f[f"{fam}_clutter_root"]["add_l4"], fam


def test_pair_map_places_leaks_where_the_theory_says():
    p = _r()["pairs"]
    on, cl = p["onleak"]["regions"], p["clutter"]["regions"]
    assert on["frac_rho_lt_1"] > 0.99 and on["add_only_wrong"] < 0.001
    assert 0.3 < cl["frac_rho_lt_1"] < 0.7 and cl["add_only_wrong"] > 0.0
    assert on["mult_only_wrong"] > 2 * cl["mult_only_wrong"]
