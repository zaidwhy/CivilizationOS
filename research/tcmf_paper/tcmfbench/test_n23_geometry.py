"""N23 unit tests: scenario geometry and the PPR baseline's mechanism, as the paper states them.

Run: python -m tcmfbench.test_n23_geometry (or pytest tcmfbench/test_n23_geometry.py)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .generator import GenConfig, generate_many

RESULTS = Path(__file__).resolve().parents[1] / "results_geometry" / "results_geometry.json"


def test_scenario_graph_is_the_four_event_chain_alone():
    for sc in generate_many(20, GenConfig(n_distractors=20, n_noise=55), base_seed=0):
        assert len(sc.events) == 4 and len(sc.edges) == 3
        kinds = [e.kind for e in sc.events]
        assert kinds[0] == "root_cause" and kinds[-1] == "crisis"


def test_committed_geometry_matches_the_paper():
    g = json.load(open(RESULTS))
    cos = g["mean_cos_to_query"]
    assert abs(cos["gold_root"]) < 0.05 and abs(cos["gold_chain"]) < 0.05
    assert round(cos["distractor"], 2) == 0.81
    assert round(g["b_root_mean"], 3) == 0.285 and round(g["rho_mean"], 3) == 0.376
    assert round(g["mult_lambda_at_means_bj0"], 1) == 5.8
    m = g["ppr_mass_by_event_kind"]
    assert m["root_cause"] < m["crisis"] < m["decision"]
    assert g["ppr_top5_label_counts"] == {"gold_chain": 50, "distractor": 200}
    mc = g["mixed_mean_cos_to_query"]
    assert round(mc["gold_semantic"], 2) == 0.83 and round(mc["distractor"], 2) == 0.54


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
