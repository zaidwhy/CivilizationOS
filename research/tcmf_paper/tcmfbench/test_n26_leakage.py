"""N26/N26b tests: under boost leakage the operator (not only the weight) decides.

Run: python -m tcmfbench.test_n26_leakage (or pytest tcmfbench/test_n26_leakage.py)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .run_decision_n27 import mcnemar_exact

ROOT = Path(__file__).resolve().parents[1]


def _leak():
    return json.load(open(ROOT / "results_leakage" / "results_leakage.json"))


def test_no_gap_without_leakage():
    a = _leak()["spurious"]["0.0"]["arms"]
    for tag in ("prox", "root"):
        assert abs(a[f"add_l4_{tag}"]["causal@5"][0] - a[f"mult_l16_{tag}"]["causal@5"][0]) < 0.005


def test_additive_beats_every_multiplicative_weight_under_false_edges():
    sp = _leak()["spurious"]
    for p in ("0.1", "0.25", "0.5", "1.0"):
        a = sp[p]["arms"]
        for tag in ("prox", "root"):
            best_mult = max(a[f"mult_l{w}_{tag}"]["recall@5"][0] for w in ("0.6", "8", "16", "32"))
            assert a[f"add_l4_{tag}"]["recall@5"][0] > best_mult


def test_gap_grows_with_the_leak_rate():
    sp = _leak()["spurious"]
    gaps = [sp[p]["arms"]["add_l4_prox"]["causal@5"][0] - sp[p]["arms"]["mult_l16_prox"]["causal@5"][0]
            for p in ("0.0", "0.1", "0.25", "0.5", "1.0")]
    assert gaps == sorted(gaps)


def test_gap_vanishes_at_the_tuned_real_text_threshold():
    a = _leak()["realtext"]["0.6"]["arms"]
    assert abs(a["add_l4_prox"]["recall@5"][0] - a["mult_l16_prox"]["recall@5"][0]) < 0.01


def test_mechanism_share_of_mult_only_unreachable_pairs():
    m = json.load(open(ROOT / "results_leakage" / "results_leakage_mechanism.json"))
    for setting in m.values():
        for v in setting.values():
            assert 0.2 < v["frac_mult_only_unreachable"] < 0.45


def test_no_multiplicative_weight_reaches_additive_under_leakage_even_in_the_limit():
    # lambda -> infinity ranks by e*b; that supremum still sits below additive at lambda=4 in all
    # 12 leaky settings (4 false-edge rates + 2 thresholds, x 2 depth weightings)
    m = json.load(open(ROOT / "results_leakage" / "results_leakage_mechanism.json"))
    leak = _leak()
    settings = [(f"spurious_p{p}", "spurious", p) for p in ("0.1", "0.25", "0.5", "1.0")] +                [(f"realtext_tau{t}", "realtext", t) for t in ("0.45", "0.5")]
    for mech_key, sect, k in settings:
        for tag in ("prox", "root"):
            add = leak[sect][k]["arms"][f"add_l4_{tag}"]["recall@5"][0]
            assert m[mech_key][tag]["mult_limit_recall5"] < add


def test_decision_rerun_reproduces_published_and_shows_the_split():
    d = json.load(open(ROOT / "results_decision_n27" / "results_decision_n27.json"))
    assert d["reproduces_published"] == {"add_l4": 0.83, "mult_l0.6": 0.5, "causal_only": 0.85}
    clean, leaky = d["clean"], d["leaky"]
    assert clean["correct"]["add_l4"] == clean["correct"]["mult_l16"]      # identical answers
    a_only, b_only, p = leaky["mcnemar_add_vs_mult16"]
    assert (a_only, b_only) == (7, 0) and p < 0.02
    assert round(leaky["acc"]["add_l4"][0], 2) == 0.68 and round(leaky["acc"]["mult_l16"][0], 2) == 0.57


def test_mcnemar_exact_known_values():
    assert mcnemar_exact([True] * 5, [True] * 5) == (0, 0, 1.0)
    a_only, b_only, p = mcnemar_exact([True] * 6 + [False] * 4, [False] * 6 + [False] * 4)
    assert (a_only, b_only) == (6, 0) and abs(p - 2 / 64) < 1e-12


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
