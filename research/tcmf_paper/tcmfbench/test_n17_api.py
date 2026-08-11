"""N17 unit tests: the public API's own verify criterion.

"A retriever written against the public API alone, with no edits to tcmfbench internals,
reproduces a known baseline's published numbers exactly." These tests register plain
functions - not calling into ``methods.py`` beyond what a stranger could read off ``mat``'s
public attributes - and check they land on Table tab:main's/tab:mixed's own published rows.

Run: python -m tcmfbench.test_n17_api (or pytest tcmfbench/test_n17_api.py)
"""
from __future__ import annotations

import sys

from . import _bootstrap  # noqa: F401
from .api import evaluate


def _semantic_retriever(mat) -> list[str]:
    """Written using only public Materialized attributes (all_ids, mem, scenario) - no import
    from methods.py, no private helper. Cosine-ranks by relevance to the query, same
    definition as rank_semantic, independently reimplemented."""
    import numpy as np
    q = np.asarray(mat.scenario.query_embedding, dtype=np.float64)
    qn = q / (np.linalg.norm(q) or 1.0)

    def cos(i):
        v = np.asarray(mat.mem[i]["embedding"], dtype=np.float64)
        vn = v / (np.linalg.norm(v) or 1.0)
        return float(np.dot(qn, vn))

    return sorted(mat.all_ids, key=cos, reverse=True)


def _oracle_causal_retriever(mat) -> list[str]:
    """A trivial 'retriever' that just returns the pool in a fixed order with every true
    causal-gold memory forced to the front - reproduces causal_only's ceiling behaviour
    (recall@5 = 1.00 in the pure regime, where every gold memory is causal) without
    reimplementing any real ranking logic."""
    gold = [i for i in mat.all_ids if i in mat.gold_ids]
    rest = [i for i in mat.all_ids if i not in mat.gold_ids]
    return gold + rest


async def _async_semantic_retriever(mat):
    return _semantic_retriever(mat)


def test_semantic_retriever_reproduces_tab_main_recall5():
    """Table tab:main: semantic_rag recall@5 = 0.00 in the pure regime (n=300)."""
    table = evaluate(_semantic_retriever, tier="pure", n=300)
    assert round(table["recall@5"][0], 2) == 0.00


def test_oracle_retriever_reproduces_tab_main_ceiling():
    """Table tab:main: causal_only (oracle) recall@5 = 1.00, root_rank = 3.0."""
    table = evaluate(_oracle_causal_retriever, tier="pure", n=300)
    assert round(table["recall@5"][0], 2) == 1.00


def test_mixed_tier_reports_causal_and_semantic_subsets():
    table = evaluate(_semantic_retriever, tier="mixed", n=300)
    assert "causal@5" in table and "semantic@5" in table
    # semantic_rag recovers semantic-gold (Table tab:mixed: 1.00) but not causal-gold (0.00)
    assert round(table["semantic@5"][0], 2) == 1.00
    assert round(table["causal@5"][0], 2) == 0.00


def test_async_retriever_is_accepted():
    table = evaluate(_async_semantic_retriever, tier="pure", n=60)
    assert round(table["recall@5"][0], 2) == 0.00


def test_unknown_tier_raises():
    try:
        evaluate(_semantic_retriever, tier="nonexistent")
        raised = False
    except ValueError:
        raised = True
    assert raised


if __name__ == "__main__":
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
