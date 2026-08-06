"""N07 unit tests: the five additional retrieval baselines (MMR, BM25, summary-buffer,
community-summary, extract-and-consolidate).

Run: python -m tcmfbench.test_n07_baselines (or pytest tcmfbench/test_n07_baselines.py)
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many


def _fake_mat(specs, query_embedding, query_text="the crisis"):
    """A minimal Materialized-like object for hand-computed cases: no citizens/graph, just
    ``mem``/``all_ids``/``scenario.query_embedding``/``scenario.query_text`` - the only fields
    the five N07 baselines read."""
    mem = {}
    all_ids = []
    for i, (mid, emb, text, importance, tick) in enumerate(specs):
        mem[mid] = {"embedding": emb, "text": text, "importance": importance, "tick": tick,
                    "label": "distractor", "topic": 0, "citizen_id": "c0"}
        all_ids.append(mid)
    scenario = SimpleNamespace(query_embedding=query_embedding, query_text=query_text)
    return M.Materialized(scenario=scenario, citizens={}, graph=None, mem=mem, all_ids=all_ids)


def _real_mat(seed=0, n_distractors=20, n_noise=55):
    cfg = GenConfig(n_distractors=n_distractors, n_noise=n_noise)
    sc = generate_many(1, cfg, base_seed=seed)[0]
    return M.materialize(sc, cfg.max_mem_per_citizen)


# --------------------------------------------------------------------------- structural

def _assert_full_permutation(order, mat):
    assert len(order) == len(mat.all_ids)
    assert set(order) == set(mat.all_ids)


def test_every_new_baseline_returns_a_full_permutation_on_a_real_scenario():
    mat = _real_mat(seed=0)
    for fn in (M.rank_mmr, M.rank_bm25, M.rank_summary_buffer,
               M.rank_community_summary, M.rank_extract_consolidate):
        _assert_full_permutation(fn(mat), mat)


def test_every_new_baseline_handles_empty_pool():
    mat = _fake_mat([], query_embedding=[1.0, 0.0])
    for fn in (M.rank_mmr, M.rank_bm25, M.rank_summary_buffer,
               M.rank_community_summary, M.rank_extract_consolidate):
        assert fn(mat) == []


# --------------------------------------------------------------------------------- MMR

def test_mmr_lambda_one_degenerates_to_pure_relevance_ranking():
    """mmr_lambda=1.0 zeroes the diversity term entirely, so MMR must produce the identical
    order to plain cosine-similarity ranking - a real materialized scenario, not toy data,
    since this is a structural identity that must hold everywhere."""
    mat = _real_mat(seed=1)
    assert M.rank_mmr(mat, mmr_lambda=1.0) == M.rank_semantic(mat)


def _unit(deg: float) -> list[float]:
    r = math.radians(deg)
    return [math.cos(r), math.sin(r)]


def test_mmr_hand_computed_prefers_diverse_second_pick():
    """Four 2-D unit vectors on the unit circle by angle from the query: q=0deg, a=10deg,
    b=15deg, c=-15deg. By this mirror construction qsim_b == qsim_c EXACTLY (both 15deg from
    q), so relevance alone cannot separate them - but b sits only 5deg from a (near-dupe) while
    c sits 25deg from a (diverse), so MMR must strictly prefer c once a is selected. a has the
    highest raw qsim (10deg < 15deg) and is picked first."""
    q = _unit(0)
    a = _unit(10)
    b = _unit(15)
    c = _unit(-15)
    mat = _fake_mat(
        [("a", a, "a", 1.0, 0), ("b", b, "b", 1.0, 0), ("c", c, "c", 1.0, 0)],
        query_embedding=q,
    )
    # hand-computed MMR scores at the second step (a already selected):
    def cos(x, y):
        x, y = np.asarray(x), np.asarray(y)
        return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))

    qsim_a, qsim_b, qsim_c = cos(q, a), cos(q, b), cos(q, c)
    assert qsim_a > qsim_b and qsim_a > qsim_c  # a picked first
    assert abs(qsim_b - qsim_c) < 1e-12         # exact tie on raw relevance, by construction
    sim_ab, sim_ac = cos(a, b), cos(a, c)
    mu = 0.5
    score_b = mu * qsim_b - (1 - mu) * sim_ab
    score_c = mu * qsim_c - (1 - mu) * sim_ac
    assert score_c > score_b, "hand-computed check: c must out-score b at the second step"

    order = M.rank_mmr(mat, mmr_lambda=mu)
    assert order[0] == "a"
    assert order[1] == "c", f"expected diverse pick c second, got {order}"
    assert order[2] == "b"


def test_mmr_lambda_zero_ignores_query_entirely_after_first_pick():
    """mmr_lambda=0.0 means every pick after the first is chosen purely to minimize similarity
    to what's already selected, regardless of query relevance."""
    q = [1.0, 0.0]
    a = [1.0, 0.0]       # highest query similarity, always picked first by np.argmax tie order
    b = [0.9, 0.0]       # similar to a, still fairly relevant to q
    c = [-1.0, 0.0]      # maximally dissimilar to a, irrelevant to q
    mat = _fake_mat(
        [("a", a, "a", 1.0, 0), ("b", b, "b", 1.0, 0), ("c", c, "c", 1.0, 0)],
        query_embedding=q,
    )
    order = M.rank_mmr(mat, mmr_lambda=0.0)
    assert order[0] == "a"
    assert order[1] == "c", f"lambda=0 should pick the most diverse-from-selected item, got {order}"


# --------------------------------------------------------------------------------- BM25

def test_bm25_hand_computed_two_doc_toy_corpus():
    """Two docs, one query term. doc_a has the term once, doc_b has it three times; doc_b is
    longer, so BM25's length normalization should partially, but not fully, cancel out the raw
    term-frequency advantage. Compute the exact BM25 formula by hand and compare."""
    k1, b = 1.5, 0.75
    docs = {"a": "cause outage database", "b": "cause cause cause spike alert page noise more"}
    mat = _fake_mat(
        [("a", [1.0, 0.0], docs["a"], 1.0, 0), ("b", [0.0, 1.0], docs["b"], 1.0, 0)],
        query_embedding=[1.0, 0.0], query_text="cause",
    )
    order = M.rank_bm25(mat, k1=k1, b=b)

    # hand-computed BM25("cause") for both docs, n_docs=2, df("cause")=2
    n_docs = 2
    df_cause = 2
    idf = math.log(1.0 + (n_docs - df_cause + 0.5) / (df_cause + 0.5))
    len_a, len_b = 3, 8
    avgdl = (len_a + len_b) / 2
    f_a, f_b = 1, 3
    score_a = idf * (f_a * (k1 + 1)) / (f_a + k1 * (1 - b + b * len_a / avgdl))
    score_b = idf * (f_b * (k1 + 1)) / (f_b + k1 * (1 - b + b * len_b / avgdl))
    assert score_b > score_a  # tf=3 beats tf=1 even after length normalization here
    assert order == ["b", "a"]

    # the ranking function itself must reproduce the exact hand-computed magnitude for doc a
    assert abs(score_a - idf * (1 * 2.5) / (1 + 1.5 * (0.25 + 0.75 * 3 / 5.5))) < 1e-9


def test_bm25_term_absent_from_all_docs_scores_zero_for_everyone():
    mat = _fake_mat(
        [("a", [1.0, 0.0], "apples oranges", 1.0, 0), ("b", [0.0, 1.0], "pears grapes", 1.0, 0)],
        query_embedding=[1.0, 0.0], query_text="zzz_not_present",
    )
    order = M.rank_bm25(mat)
    # a stable sort ties on score 0.0 for both -> order is just the input all_ids order
    assert order == ["a", "b"]


def test_bm25_case_and_punctuation_insensitive_tokenization():
    assert M._tokenize("Cause, Outage!! DB-2") == ["cause", "outage", "db", "2"]


# --------------------------------------------------------------------- summary-buffer

def test_summary_buffer_recent_window_always_ranked_first_regardless_of_similarity():
    """Even a recent memory that is embedding-orthogonal to the query must outrank every
    older memory - MemGPT-style paging keeps the recency window in context unconditionally,
    it does not re-rank the window by relevance."""
    q = [1.0, 0.0]
    recent_irrelevant = ("r", [0.0, 1.0], "recent but irrelevant", 1.0, tick_recent := 100)
    old_relevant = ("o", [1.0, 0.0], "old but perfectly relevant", 1.0, 0)
    mat = _fake_mat([old_relevant, recent_irrelevant], query_embedding=q)
    order = M.rank_summary_buffer(mat, recent_window=1, page_size=10)
    assert order[0] == "r"
    assert order[1] == "o"


def test_summary_buffer_pages_ordered_by_centroid_similarity_to_query():
    """Two pages of 2 older memories each; page A's centroid is far more similar to the query
    than page B's. Page A's memories must both precede page B's, even though B contains one
    individually-high-similarity item - the mechanism only sees the page-level summary."""
    q = [1.0, 0.0]
    # page A (ticks 10,9): both near the query -> centroid ~ (1, small)
    a1 = ("a1", [0.9, 0.1], "a1", 1.0, 10)
    a2 = ("a2", [0.8, 0.1], "a2", 1.0, 9)
    # page B (ticks 8,7): one near, one far -> centroid pulled off-axis
    b1 = ("b1", [0.95, 0.05], "b1", 1.0, 8)
    b2 = ("b2", [-0.9, 0.1], "b2", 1.0, 7)
    mat = _fake_mat([a1, a2, b1, b2], query_embedding=q)
    order = M.rank_summary_buffer(mat, recent_window=0, page_size=2)
    assert set(order[:2]) == {"a1", "a2"}
    assert set(order[2:]) == {"b1", "b2"}


# ----------------------------------------------------------------- community-summary

def test_kmeans_groups_identical_embeddings_into_the_same_cluster():
    X = np.array([
        [1.0, 0.0], [1.0, 0.0], [1.0, 0.0],   # cluster 1 (identical points)
        [0.0, 1.0], [0.0, 1.0], [0.0, 1.0],   # cluster 2 (identical points)
    ])
    labels = M._kmeans(X, k=2, seed=0)
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]


def test_kmeans_k_larger_than_n_is_clamped_not_a_crash():
    X = np.array([[1.0, 0.0], [0.0, 1.0]])
    labels = M._kmeans(X, k=10, seed=0)
    assert len(labels) == 2


def test_community_summary_ranks_the_query_aligned_cluster_first():
    q = [1.0, 0.0]
    near = [("n1", [0.95, 0.05], "n1", 1.0, 0), ("n2", [0.9, 0.1], "n2", 1.0, 0)]
    far = [("f1", [-0.9, 0.1], "f1", 1.0, 0), ("f2", [-0.95, 0.05], "f2", 1.0, 0)]
    mat = _fake_mat(near + far, query_embedding=q)
    order = M.rank_community_summary(mat, n_communities=2, seed=0)
    assert set(order[:2]) == {"n1", "n2"}
    assert set(order[2:]) == {"f1", "f2"}


# ------------------------------------------------------------- extract-and-consolidate

def test_extract_consolidate_merges_near_duplicates_keeps_highest_importance_as_rep():
    """Two near-identical embeddings (cosine ~0.999 > threshold) must merge into one group;
    the higher-importance one becomes the representative and is ranked, the lower-importance
    one trails immediately after it rather than competing independently for rank."""
    q = [1.0, 0.0]
    dup_low = ("low", [1.0, 0.0], "low", 0.2, 0)
    dup_high = ("high", [0.999, 0.001], "high", 0.9, 0)
    distinct = ("solo", [0.0, 1.0], "solo", 0.5, 0)
    mat = _fake_mat([dup_low, dup_high, distinct], query_embedding=q)
    order = M.rank_extract_consolidate(mat, dedup_threshold=0.99)
    assert order[0] == "high", f"higher-importance duplicate should be the group representative, got {order}"
    assert order[1] == "low", f"the merged duplicate should trail its representative immediately, got {order}"
    assert order[2] == "solo"


def test_extract_consolidate_high_threshold_merges_nothing():
    """At dedup_threshold=1.0 (only exact duplicates merge), distinct-but-similar embeddings
    stay in separate singleton groups and the ranking reduces to plain query-similarity order."""
    q = [1.0, 0.0]
    a = ("a", [0.99, 0.14], "a", 1.0, 0)
    b = ("b", [0.9, 0.44], "b", 1.0, 0)
    mat = _fake_mat([a, b], query_embedding=q)
    order = M.rank_extract_consolidate(mat, dedup_threshold=1.0)
    assert order == ["a", "b"]  # a is more similar to q, and nothing merged


def test_extract_consolidate_grouping_is_deterministic_and_order_independent_of_input_order():
    mat1 = _fake_mat(
        [("a", [1.0, 0.0], "a", 1.0, 0), ("b", [0.999, 0.001], "b", 0.5, 0)],
        query_embedding=[1.0, 0.0],
    )
    mat2 = _fake_mat(
        [("b", [0.999, 0.001], "b", 0.5, 0), ("a", [1.0, 0.0], "a", 1.0, 0)],
        query_embedding=[1.0, 0.0],
    )
    assert M.rank_extract_consolidate(mat1, dedup_threshold=0.99) == \
        M.rank_extract_consolidate(mat2, dedup_threshold=0.99) == ["a", "b"]


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
