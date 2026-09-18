"""N19 unit tests: BM25 rerun with the "(topic N)" text scaffolding stripped.

Run: python -m tcmfbench.test_n19_bm25_descaffold (or pytest tcmfbench/test_n19_bm25_descaffold.py)
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many
from .mixed import MixedConfig, generate_many_mixed
from .run_bm25_descaffold_n19 import _TOPIC_RE, descaffold


def _pure_mat(seed=0):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    sc = generate_many(1, cfg, base_seed=seed)[0]
    return M.materialize(sc, cfg.max_mem_per_citizen)


def _mixed_mat(seed=0):
    cfg = MixedConfig(n_distractors=20, n_noise=55)
    sc = generate_many_mixed(1, cfg, base_seed=seed)[0]
    return M.materialize(sc, cfg.max_mem_per_citizen)


def test_descaffold_removes_every_topic_suffix_pure_regime():
    mat = _pure_mat()
    d = descaffold(mat)
    for rec in d.mem.values():
        assert not _TOPIC_RE.search(rec["text"]), rec["text"]
    assert not _TOPIC_RE.search(d.scenario.query_text)
    # and the original scaffolding really was there, or this test would be vacuous
    assert any(_TOPIC_RE.search(rec["text"]) for rec in mat.mem.values())


def test_descaffold_changes_only_text():
    mat = _pure_mat()
    d = descaffold(mat)
    assert d.gold_ids == mat.gold_ids
    assert d.root_id == mat.root_id
    assert d.all_ids == mat.all_ids
    for i in mat.all_ids:
        assert d.mem[i]["embedding"] == mat.mem[i]["embedding"]
        assert d.mem[i]["importance"] == mat.mem[i]["importance"]
    assert d.scenario.query_embedding == mat.scenario.query_embedding


def test_descaffold_is_a_noop_for_bm25_on_a_pure_scenario_that_never_promotes_a_distractor_by_token():
    # A scenario built to defeat the topic-id shortcut: descaffolding removes the only shared
    # literal token between the crisis query and its distractors, so BM25's ranking of the
    # root-cause witness relative to the distractors can only improve or stay the same, never
    # get worse, when the confound is removed.
    mat = _pure_mat(seed=7)
    ranked_before = M.rank_bm25(mat, k1=0.5)
    ranked_after = M.rank_bm25(descaffold(mat), k1=0.5)
    rank_before = (ranked_before.index(mat.root_id) + 1) if mat.root_id in ranked_before else None
    rank_after = (ranked_after.index(mat.root_id) + 1) if mat.root_id in ranked_after else None
    assert rank_after is not None
    if rank_before is not None:
        assert rank_after <= rank_before


def test_mixed_regime_witness_text_never_carried_the_topic_scaffold():
    # The mixed generator's memory text templates ("witness N", "ancestor N", "symptom N", ...)
    # never embedded "(topic N)" in the first place - confirmed directly against the source
    # templates, not inferred from an unchanged score. Regression guard: if mixed.py's text
    # templates ever change to add topic-id scaffolding, this catches it.
    mat = _mixed_mat()
    for rec in mat.mem.values():
        assert not _TOPIC_RE.search(rec["text"]), rec["text"]
    assert not _TOPIC_RE.search(mat.scenario.query_text)


if __name__ == "__main__":
    test_descaffold_removes_every_topic_suffix_pure_regime()
    test_descaffold_changes_only_text()
    test_descaffold_is_a_noop_for_bm25_on_a_pure_scenario_that_never_promotes_a_distractor_by_token()
    test_mixed_regime_witness_text_never_carried_the_topic_scaffold()
    print("all N19 tests passed")
