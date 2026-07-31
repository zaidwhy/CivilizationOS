"""N04 unit tests: spurious false-ancestor edge injection + precision-damage metric.

Run: python -m tcmfbench.test_n04_spurious (or pytest tcmfbench/test_n04_spurious.py)
"""
from __future__ import annotations

import math

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .mixed import MixedConfig, generate_mixed


def test_rate_zero_injects_nothing_and_is_deterministic():
    cfg = MixedConfig(n_distractors=20, n_noise=55)  # spurious_edge_rate defaults to 0.0
    sc = generate_mixed("t0", cfg, seed=7)
    assert cfg.spurious_edge_rate == 0.0
    assert len(sc.events) == cfg.chain_len  # no extra spurious event appended
    assert len(sc.edges) == cfg.chain_len - 1  # no extra spurious edge, no dropout either
    assert not any("spurious" in ev.id for ev in sc.events)

    # same seed, same (default) config -> byte-identical scenario, twice
    sc2 = generate_mixed("t0", cfg, seed=7)
    assert [ev.embedding for ev in sc.events] == [ev.embedding for ev in sc2.events]
    assert sc.query_embedding == sc2.query_embedding
    assert [m.embedding for m in sc.memories] == [m.embedding for m in sc2.memories]
    assert sc.edges == sc2.edges


def test_rate_zero_matches_config_without_the_field_at_all():
    """A run that never touches spurious_edge_rate (as every pre-N04 script does) must be
    unaffected by the new knob existing - the whole point of gating the RNG draw."""
    cfg_explicit0 = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=0.0)
    cfg_default = MixedConfig(n_distractors=20, n_noise=55)
    sc_a = generate_mixed("tA", cfg_explicit0, seed=42)
    sc_b = generate_mixed("tA", cfg_default, seed=42)
    assert [ev.embedding for ev in sc_a.events] == [ev.embedding for ev in sc_b.events]
    assert [m.embedding for m in sc_a.memories] == [m.embedding for m in sc_b.memories]
    assert sc_a.query_embedding == sc_b.query_embedding
    assert sc_a.edges == sc_b.edges


def test_rate_one_always_injects_a_direct_false_ancestor_edge():
    cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0)
    sc = generate_mixed("t1", cfg, seed=3)
    spur = [ev for ev in sc.events if "spurious" in ev.id]
    assert len(spur) == 1
    assert (spur[0].id, sc.crisis_event_id) in sc.edges
    assert len(sc.events) == cfg.chain_len + 1
    assert len(sc.edges) == cfg.chain_len  # chain_len-1 real edges + 1 spurious


def test_rate_one_is_deterministic_given_seed():
    cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0)
    sc1 = generate_mixed("t1", cfg, seed=9)
    sc2 = generate_mixed("t1", cfg, seed=9)
    spur1 = next(ev for ev in sc1.events if "spurious" in ev.id)
    spur2 = next(ev for ev in sc2.events if "spurious" in ev.id)
    assert spur1.embedding == spur2.embedding
    assert spur1.tick == spur2.tick


def test_injected_false_ancestor_is_a_real_bfs_predecessor_after_materialize():
    """The injected edge is a genuine graph edge (not the institution-scoped weak-ancestor
    fallback), so even the `clean=True` true-BFS ancestor set is fooled by it - that is the
    whole point: a wrongly-logged edge, not a heuristic artifact."""
    cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0)
    sc = generate_mixed("t2", cfg, seed=5)
    mat = M.materialize(sc, cfg.max_mem_per_citizen)
    spur = next(ev for ev in sc.events if "spurious" in ev.id)
    ancestors = mat.graph.predecessors(sc.crisis_event_id, max_depth=4)
    assert spur.id in ancestors
    assert ancestors[spur.id] == 1  # direct predecessor of the crisis


def test_spurious_topic_matches_distractor_topic_not_any_real_ancestor_topic():
    cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0)
    sc = generate_mixed("t3", cfg, seed=11)
    spur = next(ev for ev in sc.events if "spurious" in ev.id)
    crisis = next(ev for ev in sc.events if ev.kind == "crisis")
    real_ancestor_topics = {ev.topic for ev in sc.events if ev.kind in ("root_cause", "decision")
                            and "spurious" not in ev.id}
    assert spur.topic == crisis.topic  # aligned to the crisis SURFACE topic
    assert spur.topic not in real_ancestor_topics  # never a real ancestor's topic


def test_any_in_top_k_hand_computed():
    ranked = ["a", "b", "c", "d", "e"]
    assert MT.any_in_top_k(ranked, {"c"}, 5) == 1.0
    assert MT.any_in_top_k(ranked, {"c"}, 2) == 0.0
    assert MT.any_in_top_k(ranked, {"z"}, 5) == 0.0
    assert MT.any_in_top_k(ranked, {"a", "z"}, 1) == 1.0
    assert math.isnan(MT.any_in_top_k(ranked, set(), 5))


def test_distractor_ids_matches_generator_count():
    cfg = MixedConfig(n_distractors=20, n_noise=55)
    sc = generate_mixed("t4", cfg, seed=1)
    mat = M.materialize(sc, cfg.max_mem_per_citizen)
    assert len(M.distractor_ids(mat)) == cfg.n_distractors
    assert M.distractor_ids(mat).isdisjoint(mat.gold_ids)


if __name__ == "__main__":
    import sys
    import traceback

    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
