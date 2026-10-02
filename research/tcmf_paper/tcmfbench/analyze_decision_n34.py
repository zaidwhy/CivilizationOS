"""N34 analysis: the decision tests at n=120 with Holm-corrected exact McNemar tests.

Reads results_decision_n34 (retrieval arms, three judges) and results_decision_n34b (decisions from
LLM-built graphs) and writes results_decision_n34/results_decision_n34_summary.json and
RESULTS_DECISION_N34_SUMMARY.md. Holm-Bonferroni is applied within each family of tests:
  family 1: additive vs multiplicative(16), leaky retrieval, one test per judge (3 tests);
  family 2: true chain vs LLM-built graph, additive, per depth weighting, per judge and graph (6 tests
            per weighting).

    python -m tcmfbench.analyze_decision_n34
"""
from __future__ import annotations

import json
from pathlib import Path

from .run_decision_n27 import mcnemar_exact

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "results_decision_n34" / "results_decision_n34.json"
B = ROOT / "results_decision_n34b" / "results_decision_n33.json"
OUT = ROOT / "results_decision_n34"
SHORT = {"qwen2.5:3b-instruct": "Qwen2.5-3B", "meta-llama/llama-3.3-70b-instruct": "Llama-3.3-70B",
         "google/gemini-2.5-flash": "Gemini-2.5-Flash"}


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def main():
    a = json.loads(A.read_text(encoding="utf-8"))
    b = json.loads(B.read_text(encoding="utf-8"))
    out = {"retrieval": {}, "graphs": {}}

    ps, keys = [], []
    for judge, r in a.items():
        add, mult = r["leaky"]["correct"]["add_l4"], r["leaky"]["correct"]["mult_l16"]
        n = len(add)
        x, y, p = mcnemar_exact(add, mult)
        out["retrieval"][judge] = {"n": n, "add": sum(add) / n, "mult16": sum(mult) / n,
                                   "add_only": x, "mult_only": y, "p": p}
        ps.append(p)
        keys.append(judge)
    for k, adj in zip(keys, holm(ps)):
        out["retrieval"][k]["p_holm"] = adj

    for tag in ("prox", "root"):
        ps, keys = [], []
        for judge, r in b.items():
            for g in ("llama-70b", "gemini-flash"):
                t = r["correct"][f"true chain|add|{tag}"]
                c = r["correct"][f"{g}|add|{tag}"]
                n = len(t)
                x, y, p = mcnemar_exact(t, c)      # x: true chain right and graph wrong
                out["graphs"][f"{judge}|{g}|{tag}"] = {
                    "n": n, "true": sum(t) / n, "graph": sum(c) / n, "loss_points": 100 * (sum(t) - sum(c)) / n,
                    "true_only": x, "graph_only": y, "p": p}
                ps.append(p)
                keys.append(f"{judge}|{g}|{tag}")
        for k, adj in zip(keys, holm(ps)):
            out["graphs"][k]["p_holm"] = adj

    (OUT / "results_decision_n34_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    lines = ["# N34 summary: n=120, Holm-corrected exact McNemar", "",
             "## Leaky retrieval: additive 4 vs multiplicative 16 (3 tests)", "",
             "| judge | add | mult16 | add-only / mult-only | p | p (Holm) |", "|---|---|---|---|---|---|"]
    for j, v in out["retrieval"].items():
        lines.append(f"| {SHORT[j]} | {v['add']:.3f} | {v['mult16']:.3f} | {v['add_only']}/{v['mult_only']} | "
                     f"{v['p']:.4f} | {v['p_holm']:.4f} |")
    for tag in ("prox", "root"):
        lines += ["", f"## True chain vs LLM-built graph, additive, {tag} weights (6 tests)", "",
                  "| judge | graph | true | graph acc | loss (pts) | true-only/graph-only | p | p (Holm) |",
                  "|---|---|---|---|---|---|---|---|"]
        for k, v in out["graphs"].items():
            j, g, t = k.split("|")
            if t == tag:
                lines.append(f"| {SHORT[j]} | {g} | {v['true']:.3f} | {v['graph']:.3f} | {v['loss_points']:+.1f} | "
                             f"{v['true_only']}/{v['graph_only']} | {v['p']:.4f} | {v['p_holm']:.4f} |")
    (OUT / "RESULTS_DECISION_N34_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
