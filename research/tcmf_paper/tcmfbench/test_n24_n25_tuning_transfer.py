"""N24/N25 tests: wide-grid held-out tuning, and transfer of a fixed fusion weight.

Run: python -m tcmfbench.test_n24_n25_tuning_transfer (or pytest on this file)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import run_tuned
from .run_tuned_wide_n24 import WIDE_GRIDS

ROOT = Path(__file__).resolve().parents[1]


def test_wide_grids_keep_the_n03_budget_and_contain_the_old_selection():
    for name, grid in WIDE_GRIDS.items():
        assert len(grid) == run_tuned.SWEEP_BUDGET
    assert 2.4 in WIDE_GRIDS["tcmf_mult_lambda"]      # N03's boundary pick is still a candidate
    assert 0.95 in WIDE_GRIDS["graph_ppr_alpha"]
    assert 2.0 in WIDE_GRIDS["rrf_c"]


def test_wide_tuning_lets_multiplication_match_additive_on_test():
    r = json.load(open(ROOT / "results_main_tuned_wide" / "results_tuned.json"))
    assert r["selected"]["tcmf_mult_lambda"] == 16.0   # interior of the widened grid
    assert r["selected"]["graph_ppr_alpha"] == 0.95
    # RRF still selects its smallest c, but has plateaued: shrinking c further gains < 0.01
    ts = {float(k): v for k, v in r["tune_scores"]["rrf_c"].items()}
    assert ts[0.1] - ts[0.25] < 0.01
    main = r["test_main"]
    assert round(main["tcmf_mult"]["recall@5"]["mean"], 2) == 1.00
    assert round(main["tcmf_add"]["recall@5"]["mean"], 2) == 1.00


def test_transfer_large_mult_weight_matches_additive_on_clean_graphs():
    t = json.load(open(ROOT / "results_transfer" / "results_transfer.json"))
    for setting in ("mixed_pool80", "realtext_6dom", "realtext_8dom_test"):
        a = t[setting]["arms"]
        assert abs(a["mult_l16"]["recall@5"][0] - a["add_l4"]["recall@5"][0]) < 0.01


def test_operator_gap_under_boost_leakage():
    # Proposition 1(a): with one false edge per scenario, no multiplicative weight recovers the
    # causal evidence, while additive keeps what the causal score alone keeps.
    a = json.load(open(ROOT / "results_transfer" / "results_transfer.json"))["mixed_pool80_spurious_p1"]["arms"]
    assert max(a[k]["causal@5"][0] for k in ("mult_l0.6", "mult_l8", "mult_l16")) < 0.01
    assert a["add_l4"]["causal@5"][0] > 0.30
    assert abs(a["add_l4"]["causal@5"][0] - a["causal_only"]["causal@5"][0]) < 0.02


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
