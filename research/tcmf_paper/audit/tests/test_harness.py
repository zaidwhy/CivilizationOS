"""Checks that the audit harness measures what it says, before any result is trusted."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tcmfaudit import graphs
from tcmfaudit import retrievers as R
from tcmfaudit.run_retrieval import TOP_K, score
from tcmfaudit.stats import holm, mcnemar_exact, paired_diff
from tcmfaudit.world import WorldConfig, generate

DEFAULT = WorldConfig()


def assert_same_ranking_up_to_exact_ties(w, og, knobs, label, production_rank=R.rank_tcmf_deployed):
    """The re-implementation and production may order two memories differently only when
    their fused scores are exactly equal (production breaks ties by citizen, this by index)."""
    scores = R.tcmf_variant_scores(w, og, **knobs)
    mine, production = R.rank_tcmf_variant(w, og, **knobs), production_rank(w, og)
    for a, b in zip(mine, production):
        assert a == b or scores[a] == scores[b], label


def test_topic_geometry_matches_the_knobs():
    for rho in (0.0, 0.5):
        cos = []
        for seed in range(200):
            w = generate(replace(DEFAULT, rho=rho), seed)
            root_event = w.ev_emb[DEFAULT.depth - 1]
            cos.append(float(root_event @ w.ev_emb[w.crisis]))
        # event = 0.95 * topic + noise, so event-event cosine is 0.95^2 * rho
        assert np.mean(cos) == pytest.approx(0.95 * 0.95 * rho, abs=0.03)


def test_truth_is_a_single_chain_ending_at_the_crisis():
    w = generate(replace(DEFAULT, depth=4), 3)
    assert len(w.true_edges) == 4
    assert graphs.ancestors(graphs.oracle(w)) == {0: 1, 1: 2, 2: 3, 3: 4}
    ticks = [w.ev_tick[i] for i in (3, 2, 1, 0, w.crisis)]
    assert ticks == sorted(ticks), "a cause must not happen after its effect"


def test_random_sits_at_k_over_n_and_oracle_at_one():
    hits, oracle_hits = [], []
    for seed in range(600):
        w = generate(DEFAULT, seed)
        og = graphs.oracle(w)
        hits.append(score(w, R.rank_random(w, og, seed=seed))["causal_recall"])
        oracle_hits.append(score(w, R.rank_oracle(w, og))["root_hit"])
    assert np.mean(hits) == pytest.approx(TOP_K / w.n, abs=0.02)
    assert np.mean(oracle_hits) == 1.0


@pytest.mark.parametrize("mode", ["chain_only", "oracle", "noisy", "shuffled", "deployed", "no_crisis_id"])
def test_reimplementation_ranks_exactly_like_the_deployed_retriever(mode):
    for seed in range(40):
        w = generate(replace(DEFAULT, rho=0.3, rho_decoy=0.3), seed)
        rng = np.random.default_rng(seed)
        og = {
            "chain_only": lambda: graphs.chain_only(w),
            "oracle": lambda: graphs.oracle(w),
            "noisy": lambda: graphs.noisy(w, rng, 0.3, 2),
            "shuffled": lambda: graphs.shuffled(w, rng),
            "deployed": lambda: graphs.deployed(w),
            "no_crisis_id": lambda: graphs.no_crisis_id(w),
        }[mode]()
        assert_same_ranking_up_to_exact_ties(w, og, {}, (mode, seed))


CURRENT = {"weak": 0.5, "threshold": 0.60, "max_depth": 8}


@pytest.mark.parametrize("mode", ["chain_only", "oracle", "noisy", "shuffled", "deployed", "no_crisis_id"])
def test_reimplementation_tracks_the_retriever_as_it_ships_today(mode):
    """Fails when production's defaults move again, which is the signal to re-measure."""
    for seed in range(40):
        w = generate(replace(DEFAULT, depth=1 + seed % 6, rho=0.3, rho_decoy=0.3), seed)
        rng = np.random.default_rng(seed)
        og = {
            "chain_only": lambda: graphs.chain_only(w),
            "oracle": lambda: graphs.oracle(w),
            "noisy": lambda: graphs.noisy(w, rng, 0.3, 2),
            "shuffled": lambda: graphs.shuffled(w, rng),
            "deployed": lambda: graphs.deployed(w),
            "no_crisis_id": lambda: graphs.no_crisis_id(w),
        }[mode]()
        assert_same_ranking_up_to_exact_ties(w, og, CURRENT, (mode, seed), R.rank_tcmf_current)


def test_paper_configuration_matches_production_where_the_weak_rule_cannot_act():
    """Production has no switch for the weak-ancestor rule, so the paper configuration is the
    re-implementation with it off. On a chain-only graph the rule adds nothing, so the two
    must rank identically there; that is the only place they can be compared."""
    for seed in range(60):
        w = generate(replace(DEFAULT, depth=1 + seed % 4, rho=0.2), seed)
        og = graphs.chain_only(w)
        assert_same_ranking_up_to_exact_ties(w, og, {"weak": False}, seed)


def test_deployed_linker_is_the_production_function():
    w = generate(DEFAULT, 0)
    og = graphs.deployed(w)
    assert all(effect == w.crisis for _, effect in og.edges), "engine links only into the crisis"


def test_noisy_graph_never_links_a_decoy_backward_in_time():
    for seed in range(50):
        w = generate(DEFAULT, seed)
        og = graphs.noisy(w, np.random.default_rng(seed), 0.0, 4)
        for cause, effect in og.edges:
            assert w.ev_tick[cause] < w.ev_tick[effect]


def test_stats_on_known_inputs():
    a = np.array([1] * 30 + [0] * 10)
    b = np.array([0] * 30 + [1] * 10)
    assert mcnemar_exact(a, b) < 0.01
    assert mcnemar_exact(a, a) == 1.0
    d = paired_diff(np.ones(100), np.zeros(100))
    assert d["diff"] == 1.0 and d["p"] < 0.001
    same = paired_diff(np.arange(100) % 2, (np.arange(100) + 1) % 2)
    assert same["lo"] < 0 < same["hi"]
    assert holm({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
