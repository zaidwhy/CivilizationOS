"""N01 unit tests: hand-computed known answers for the analytic random baseline and for the
multi-seed pool construction. Run directly:

    python -m tcmfbench.test_n01_scale

(from ``research/tcmf_paper``, with the project venv on PATH) or via pytest if pytest is
available. No scipy; pure numpy/stdlib only, per the standing rules in NIGHT_QUEUE.md.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401
from .generator import GenConfig, generate_many
from .metrics import analytic_random_recall_at_k
from .mixed import MixedConfig, generate_many_mixed
from .methods import materialize


def test_analytic_random_recall_hand_computed() -> None:
    # pool=10, k=3 -> 3/10 = 0.3 exactly, independent of gold count.
    assert analytic_random_recall_at_k(pool_size=10, k=3) == 0.3
    # pool=78 (the N01 realistic pool: 3 gold + 20 distractors + 55 noise), k=10.
    got = analytic_random_recall_at_k(pool_size=78, k=10)
    assert abs(got - (10 / 78)) < 1e-12
    assert abs(got - 0.1282) < 1e-4
    # old pool=17 (pre-N01), k=10 -> matches the historical ~0.58 note in NIGHT_QUEUE.md.
    assert abs(analytic_random_recall_at_k(pool_size=17, k=10) - 0.5882) < 1e-3
    # k larger than the pool must cap at 1.0, not exceed it.
    assert analytic_random_recall_at_k(pool_size=5, k=10) == 1.0


def test_pool_size_matches_configured_distractors_and_noise() -> None:
    """N01's Env check: confirm materialize() does not silently re-cap the enlarged pool."""
    cfg = GenConfig(n_distractors=20, n_noise=55)
    gold_per_scenario = cfg.chain_len - 1  # witnesses_per_ancestor=1
    expected_pool = gold_per_scenario + cfg.n_distractors + cfg.n_noise
    assert expected_pool == 78
    sc = generate_many(3, cfg, base_seed=0)[0]
    assert len(sc.memories) == expected_pool
    mat = materialize(sc, cfg.max_mem_per_citizen)
    # the real pipeline's candidate pool (all_ids) must equal the full generated pool - if this
    # assertion ever fails, the per-citizen prune is silently re-capping the enlarged pool.
    assert len(mat.all_ids) == expected_pool


def test_mixed_pool_size_matches_configured_distractors_and_noise() -> None:
    cfg = MixedConfig(n_distractors=20, n_noise=55)
    expected_pool = cfg.total_gold() + cfg.n_distractors + cfg.n_noise
    assert expected_pool == 80
    sc = generate_many_mixed(3, cfg, base_seed=0)[0]
    assert len(sc.memories) == expected_pool
    mat = materialize(sc, cfg.max_mem_per_citizen)
    assert len(mat.all_ids) == expected_pool


def test_seed_stride_gives_disjoint_scenarios() -> None:
    """Multi-seed harness contract: distinct --seeds entries must not silently regenerate the
    same scenarios (which would happen if the stride were smaller than --n)."""
    stride = 100_000
    cfg = GenConfig()
    n = 300
    seeds = [0, 1, 2]
    seen_embeddings = set()
    for s in seeds:
        for sc in generate_many(n, cfg, base_seed=s * stride):
            key = tuple(round(x, 6) for x in sc.query_embedding[:4])
            assert key not in seen_embeddings, "seed stride collision: scenarios not disjoint"
            seen_embeddings.add(key)


def _run_all() -> None:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
