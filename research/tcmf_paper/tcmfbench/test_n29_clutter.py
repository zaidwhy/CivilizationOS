"""N29 tests: cluttered causal graphs.

Run: python -m pytest tcmfbench/test_n29_clutter.py
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .clutter import ClutterConfig, generate_clutter_mixed
from .mixed import MixedConfig, generate_mixed

ROOT = Path(__file__).resolve().parents[1]


def _r():
    return json.load(open(ROOT / "results_clutter_n29" / "results_clutter_n29.json"))


def test_clutter_keeps_memories_query_and_crisis_last():
    mc = MixedConfig(n_distractors=20, n_noise=55)
    base = generate_mixed("m0", mc, 7)
    cl = generate_clutter_mixed("m0", mc, ClutterConfig(n_background=16, n_false_edges=4), 7)
    assert [m.embedding for m in cl.memories] == [m.embedding for m in base.memories]
    assert cl.query_embedding == base.query_embedding
    assert cl.events[-1].id == cl.crisis_event_id  # scorers read "now" off the last event
    assert len(cl.events) == len(base.events) + 16


def test_unconnected_background_changes_nothing():
    s = _r()["synthetic"]
    for tag in ("prox", "root"):
        assert s[f"bg16_k0_{tag}"]["add_l4"] == s[f"clean_{tag}"]["add_l4"]
        assert s[f"bg16_k0_{tag}"]["mean_deepest_ancestor"] == 3.0


def test_false_edges_degrade_every_fusion_monotonically():
    s = _r()["synthetic"]
    for tag in ("prox", "root"):
        seq = [s[f"{k}_{tag}"]["add_l4"] for k in ("clean", "bg16_k1", "bg16_k2", "bg16_k4", "bg16_k8")]
        assert all(a > b for a, b in zip(seq, seq[1:])), seq
        assert s[f"bg16_k4_{tag}"]["add_l4"] < s[f"bg16_k4_{tag}"]["semantic"]


def test_off_topic_clutter_favours_multiplication():
    s = _r()["synthetic"]
    for k in ("bg16_k1", "bg16_k2", "bg16_k4", "bg16_k8", "messy_bg32_k4_d.2"):
        for tag in ("prox", "root"):
            v = s[f"{k}_{tag}"]
            assert v["mult_raw_l16"] > v["add_l4"], (k, tag)
            assert v["add_l4_minus_best_mult_ci"][2] < 0, (k, tag)  # CI upper bound below 0


def test_clutter_leaves_graph_ancestors_intact():
    mc = MixedConfig(n_distractors=20, n_noise=55)
    sc = generate_clutter_mixed("m0", mc, ClutterConfig(n_background=16, n_false_edges=4), 3)
    mat = M.materialize(sc, mc.max_mem_per_citizen)
    anc = M._ancestor_map(mat, clean=True)
    chain = {e.id for e in sc.events if not e.id.split("_")[-1].startswith("bg")} - {sc.crisis_event_id}
    assert chain <= set(anc)
