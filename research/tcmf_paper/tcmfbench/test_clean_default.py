"""Audit L5 regression test: the ``clean`` flag of the causal boost.

Every operator in ``methods`` now defaults to ``clean=True``. The multiplicative operator used to
default to ``clean=False`` (the shipped institution-scoped fallback), and several run scripts
relied on that default. The fallback only re-adds chain events the backward search already
found, so on the benchmark tiers both settings give identical ancestor maps: 0 of 150 differ
(50 pure, 50 mixed without and 50 with an on-topic false edge in every scenario), and the
multiplicative ranking at lambda=16 is identical on all 50 pure scenarios. The default change
therefore leaves every committed result unchanged; this test fails if that stops being true.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many
from .mixed import MixedConfig, generate_many_mixed


def _pure():
    cfg = GenConfig()
    return [M.materialize(s, cfg.max_mem_per_citizen) for s in generate_many(50, cfg, base_seed=0)]


def _mixed(p):
    cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=p)
    return [M.materialize(s, cfg.max_mem_per_citizen) for s in generate_many_mixed(50, cfg, base_seed=0)]


def test_clean_flag_changes_no_ancestor_map_on_the_benchmark_tiers():
    mats = _pure() + _mixed(0.0) + _mixed(1.0)
    differ = sum(M._ancestor_map(m, clean=False) != M._ancestor_map(m, clean=True) for m in mats)
    assert (differ, len(mats)) == (0, 150)


def test_multiplicative_ranking_identical_under_both_clean_settings():
    mats = _pure()
    differ = sum(M.rank_tcmf_multiplicative(m, lam=16.0, clean=False)
                 != M.rank_tcmf_multiplicative(m, lam=16.0, clean=True) for m in mats)
    assert differ == 0


def test_every_operator_defaults_to_clean():
    import inspect
    for fn in (M._ancestor_map, M._causal_boosts, M.rank_causal_only, M.rank_tcmf_multiplicative,
               M.rank_tcmf_additive, M.rank_tcmf_normalized_multiplicative, M.rank_tcmf_rrf,
               M.rank_tcmf_ablation):
        assert inspect.signature(fn).parameters["clean"].default is True, fn.__name__
