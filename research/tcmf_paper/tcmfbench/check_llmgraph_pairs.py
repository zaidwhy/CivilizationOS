"""Audit L8: recompute the (rho, beta) pair quadrants of results_llmgraph_n31.json offline.

The committed file shows both_wrong and both_right exchanged between the proximate- and the
root-favoring blocks (Llama: 0.075 / 0.717 vs 0.717 / 0.075). This script rebuilds every
model's graph from its committed graphs_*.json, re-runs ``run_llmgraph_n31._eval`` for both
depth weightings, and prints the stored and recomputed quadrant fractions side by side, plus
how many pairs move between quadrants when only the depth weighting changes. No model calls.

Result (2026-10-22): every stored fraction reproduces exactly for all four models, so the file is
correct and the generator is not swapped. The pairs are the same under both weightings (rho
depends only on the episodic score); only beta = b_j / b_i changes. Root-favoring weights give
the deepest ancestors the largest weight, and the LLMs' false ancestors sit deep in the graph, so
leaked boosts overtake the causal ones (beta >= 1) and most pairs move from both_right to
both_wrong. For Llama 37 of 53 pairs move that way and 4 move back, which is why its two blocks
look like a mirror image (0.075 / 0.717 and 0.717 / 0.075); the other models are not mirrored.

    python -m tcmfbench.check_llmgraph_pairs
"""
from __future__ import annotations

import json

import numpy as np

from . import _bootstrap  # noqa: F401
from . import llm_graph as G
from . import methods as M
from .realtext import RealConfig
from .run_llmgraph_n31 import OUT, _eval, _summ, scenarios

QUADS = ("mult_only_wrong", "add_only_wrong", "both_wrong", "both_right")


def _quad(rho: float, beta: float) -> str:
    if beta < 1 and rho <= beta:
        return "mult_only_wrong"
    if beta > 1 and rho > beta:
        return "add_only_wrong"
    if beta >= 1 and rho <= beta:
        return "both_wrong"
    if beta < 1 and rho > beta:
        return "both_right"
    return "neither"  # beta == 1 and rho > 1


def main() -> dict:
    stored = json.loads((OUT / "results_llmgraph_n31.json").read_text(encoding="utf-8"))["models"]
    scs = scenarios()
    rcfg = RealConfig()
    report = {}
    for model in stored:
        safe = model.replace(":", "_").replace("/", "_")
        graphs = json.loads((OUT / f"graphs_{safe}.json").read_text(encoding="utf-8"))
        by_id = {g["scenario"]: [tuple(e) for e in g["edges"]] for g in graphs}
        mats = [M.materialize(G.with_edges(sc, by_id[sc.scenario_id]), rcfg.max_mem_per_citizen)
                for sc in scs]
        per = {}
        for fr, tag in ((False, "prox"), (True, "root")):
            ev = [_eval(m, fr) for m in mats]
            pairs = [p for _, ps in ev for p in ps]
            per[tag] = pairs
            got = _summ([r for r, _ in ev], pairs)["pairs"]
            want = stored[model][f"retrieval_{tag}"]["pairs"]
            print(f"{model:40s} {tag}: n {want['n']} -> {got['n']}  " + "  ".join(
                f"{q} {want[q]:.4f}->{got[q]:.4f}" for q in QUADS))
            report[f"{model}/{tag}"] = {"stored": want, "recomputed": got}
        # same pairs in the same order under both weightings (rho depends on e only)
        a, b = np.array(per["prox"]), np.array(per["root"])
        assert a.shape == b.shape and np.allclose(a[:, 0], b[:, 0])
        moves = {}
        for (r, bp), (_, br) in zip(per["prox"], per["root"]):
            k = f"{_quad(r, bp)} -> {_quad(r, br)}"
            moves[k] = moves.get(k, 0) + 1
        print(f"{'':40s} moves prox -> root: {moves}")
        report[f"{model}/moves"] = moves
    return report


if __name__ == "__main__":
    main()
