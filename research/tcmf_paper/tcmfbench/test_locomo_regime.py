"""N18 tests: the LoCoMo regime measurement's parsing and scoring logic.

CLOUD-OK by design. The embedding step is LOCAL-ONLY (needs Ollama), so everything here runs
on hand-built vectors and a synthetic LoCoMo-shaped fixture instead. That keeps the part most
likely to be silently wrong - evidence resolution and rank/recall arithmetic - under test
everywhere.

Run: python -m tcmfbench.test_locomo_regime (or pytest tcmfbench/test_locomo_regime.py)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .locomo_regime import (cosine, gold_units, load_locomo, rank_units, score_question,
                            units_for)

FIXTURE = [{
    "sample_id": "conv0",
    "conversation": {
        "session_1_date_time": "1 Jan, 2024",
        "session_1": [
            {"speaker": "A", "dia_id": "D1:1", "text": "alpha"},
            {"speaker": "B", "dia_id": "D1:2", "text": "beta"},
        ],
        "session_2_date_time": "2 Jan, 2024",
        "session_2": [
            {"speaker": "A", "dia_id": "D2:1", "text": "gamma"},
            {"speaker": "B", "dia_id": "D2:2", "text": ""},          # dropped: no text
        ],
    },
    "qa": [
        {"question": "q multi", "category": 1, "evidence": ["D1:1", "D2:1"]},
        {"question": "q single-span", "category": 1, "evidence": ["D1:1"]},
        {"question": "q wrong category", "category": 4, "evidence": ["D1:1", "D2:1"]},
        {"question": "q dangling", "category": 1, "evidence": ["D1:1", "D9:9"]},
    ],
}]


def _load_fixture():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "locomo10.json"
        p.write_text(json.dumps(FIXTURE), encoding="utf-8")
        return load_locomo(p)


def test_parsing_drops_empty_turns_and_date_keys():
    conv = _load_fixture()[0]
    assert [i for i, _ in conv.turns] == ["D1:1", "D1:2", "D2:1"]     # D2:2 has no text
    assert [k for k, _ in conv.sessions] == ["session_1", "session_2"]
    assert conv.turn_to_session["D2:1"] == "session_2"


def test_session_text_concatenates_with_speakers():
    conv = _load_fixture()[0]
    text = dict(conv.sessions)["session_1"]
    assert text == "A: alpha\nB: beta"


def test_question_filter_keeps_only_multihop_with_resolvable_evidence():
    """Single-span, wrong-category and dangling-evidence questions must all be excluded -
    a dangling reference would otherwise raise a KeyError deep inside scoring."""
    conv = _load_fixture()[0]
    assert [q["question"] for q in conv.questions] == ["q multi"]


def test_gold_units_maps_turns_to_their_sessions():
    conv = _load_fixture()[0]
    q = conv.questions[0]
    assert gold_units(q, conv, "turn") == {"D1:1", "D2:1"}
    assert gold_units(q, conv, "session") == {"session_1", "session_2"}


def test_units_for_matches_the_requested_granularity():
    conv = _load_fixture()[0]
    assert len(units_for(conv, "turn")) == 3
    assert len(units_for(conv, "session")) == 2


def test_cosine_hand_computed():
    assert abs(cosine([1, 0], [1, 0]) - 1.0) < 1e-12
    assert abs(cosine([1, 0], [0, 1]) - 0.0) < 1e-12
    assert abs(cosine([1, 0], [-1, 0]) + 1.0) < 1e-12
    assert cosine([0, 0], [1, 0]) == 0.0                 # zero vector must not divide by zero


def test_rank_units_is_one_based_and_ordered_by_similarity():
    q = [1.0, 0.0]
    units = [("far", [0.0, 1.0]), ("near", [1.0, 0.0]), ("mid", [1.0, 1.0])]
    ranks = rank_units(q, units)
    assert ranks == {"near": 1, "mid": 2, "far": 3}


def test_score_question_hand_computed():
    """gold at ranks 2 and 7 out of 10: recall@5 catches one of two, recall@10 both."""
    ranks = {f"u{i}": i for i in range(1, 11)}
    out = score_question(ranks, {"u2", "u7"})
    assert out["best_gold_rank"] == 2
    assert out["worst_gold_rank"] == 7
    assert out["pool_size"] == 10
    assert out["recall@5"] == 0.5
    assert out["recall@10"] == 1.0


def test_score_question_all_gold_in_top_k():
    ranks = {f"u{i}": i for i in range(1, 11)}
    out = score_question(ranks, {"u1", "u3"})
    assert out["recall@5"] == 1.0
    assert out["worst_gold_rank"] == 3


def test_worst_gold_rank_is_the_retrieval_depth_needed():
    """The headline statistic must equal the smallest k with recall@k == 1."""
    ranks = {f"u{i}": i for i in range(1, 21)}
    gold = {"u4", "u11", "u2"}
    out = score_question(ranks, gold, ks=(11,))
    assert out["worst_gold_rank"] == 11
    assert out["recall@11"] == 1.0


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [getattr(mod, n) for n in dir(mod) if n.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
