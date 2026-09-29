"""N31/N31b/N32 tests: LLM-built causal graphs and the decision test with stronger judges.

These read the committed results (the paid calls are cached, not re-made).
Run: python -m pytest tcmfbench/test_n31_n32.py
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import llm_graph as G

ROOT = Path(__file__).resolve().parents[1]
PAID = ["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.5-flash"]


def _j(*p):
    return json.loads((ROOT.joinpath(*p)).read_text(encoding="utf-8"))


def test_parser_reads_only_the_last_causes_line():
    assert G.parse_causes("I think 3 matters.\nCAUSES: 2, 5, 99", 10) == [2, 5]
    assert G.parse_causes("CAUSES: NONE", 10) == []
    assert G.parse_causes("no line here 4", 10) == []


def test_llm_graphs_are_complete_but_imprecise():
    for m in PAID:
        v = _j("results_llmgraph_n31", f"model_{m.replace('/', '_')}.json")[m]
        assert v["ancestor_recall"] > 0.9 and v["root_in_ancestors"] == 1.0, m
        assert v["ancestor_precision"] < 0.6, m


def test_false_ancestors_hurt_only_once_they_have_memories():
    orig = _j("results_llmgraph_n31", "results_llmgraph_n31.json")
    b = _j("results_llmgraph_n31", "results_llmgraph_n31b.json")["graphs"]
    for m in PAID:
        v = orig["models"][m]
        assert abs(v["retrieval_prox"]["add_l4"] - orig["reference"]["true_prox"]["add_l4"]) < 0.03
        name = m.replace("/", "_")
        loss_prox = b["true chain|prox"]["add_l4"] - b[f"{name}|prox"]["add_l4"]
        loss_root = b["true chain|root"]["add_l4"] - b[f"{name}|root"]["add_l4"]
        assert 0.02 < loss_prox < 0.08 and loss_root > 0.2, m
        for tag in ("prox", "root"):
            assert abs(b[f"{name}|{tag}"]["add_l4"] - b[f"{name}|{tag}"]["mult_l16"]) < 0.025, (m, tag)


def test_stronger_judges_clean_equivalence_and_leaky_split():
    d = _j("results_decision_n32", "results_decision_n32.json")
    for m in PAID:
        a = d[m]["clean"]["acc"]
        assert abs(a["add_l4"][0] - a["mult_l16"][0]) <= 0.021, m
    g = d["google/gemini-2.5-flash"]["leaky"]
    assert g["acc"]["add_l4"][0] > g["acc"]["mult_l16"][0] and g["mcnemar_add_vs_mult16"][2] < 0.05
    ll = d["meta-llama/llama-3.3-70b-instruct"]["leaky"]["acc"]
    assert abs(ll["add_l4"][0] - ll["mult_l16"][0]) < 0.03


def test_paid_spend_stayed_under_the_cap():
    led = _j("results_openrouter", "ledger.json")
    assert led["total_usd"] < 1.50


def test_small_models_buy_less_recall_and_cost_more_retrieval():
    d = _j("results_llmgraph_n31", "results_llmgraph_n31.json")["models"]
    for m in ("qwen2.5:3b-instruct", "mistral:7b"):
        v = d[m]
        assert v["ancestor_recall"] < 0.7 and v["ancestor_precision"] < 0.5, m
        r = v["retrieval_prox"]
        assert r["add_l4"] < 0.5 and abs(r["add_l4"] - r["mult_l16"]) < 0.01, m
