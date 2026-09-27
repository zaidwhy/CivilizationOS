"""N23: scenario geometry and the PPR baseline's mechanism, measured rather than described.

On the pure regime at the realistic pool (seed 0, 300 scenarios for cosines; the first 50 of them
for PPR mass, which is slower): mean cosine of each memory type to the crisis query, mean root
boost and episodic ratio (for the b(j)=0 form of Proposition 1), how the personalized-PageRank
mass splits across the four chain events, and which memory labels fill PPR's top five.

Run: python -m tcmfbench.run_geometry_n23
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many

OUT = Path(__file__).resolve().parents[1] / "results_geometry"


def main(n=300, n_ppr=50):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    cos = {"gold_root": [], "gold_chain": [], "distractor": [], "noise": []}
    b_root, rho = [], []
    mass = Counter()
    top5 = Counter()
    for k, sc in enumerate(generate_many(n, cfg, base_seed=0)):
        mat = M.materialize(sc, cfg.max_mem_per_citizen)
        for m in sc.memories:
            cos[m.label].append(M._cosine(m.embedding, sc.query_embedding))
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, threshold=0.45, clean=True, favor_root=False)
        non_gold = [i for i in mat.all_ids if i not in mat.gold_ids]
        b_root.append(b[mat.root_id])
        rho.append(e[mat.root_id] / max(e[i] for i in non_gold))
        if k < n_ppr:
            sims = {ev.id: max(0.0, M._cosine(sc.query_embedding, ev.embedding)) for ev in sc.events}
            ex = {i: math.exp(4.0 * v) for i, v in sims.items()}
            tot = sum(ex.values())
            ppr = M._personalized_pagerank([ev.id for ev in sc.events], list(sc.edges),
                                           {i: v / tot for i, v in ex.items()}, alpha=0.85)
            for ev in sc.events:
                mass[ev.kind] += ppr[ev.id] / n_ppr
            for i in M.rank_graph_ppr(mat)[:5]:
                top5[mat.mem[i]["label"]] += 1
    summary = {
        "n": n, "n_ppr": n_ppr,
        "graph_events": len(sc.events), "graph_edges": len(sc.edges),
        "mean_cos_to_query": {k: float(np.mean(v)) for k, v in cos.items()},
        "b_root_mean": float(np.mean(b_root)), "rho_mean": float(np.mean(rho)),
        "mult_lambda_at_means_bj0": float((1 - np.mean(rho)) / (np.mean(rho) * np.mean(b_root))),
        "ppr_mass_by_event_kind": dict(mass),
        "ppr_top5_label_counts": dict(top5),
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "results_geometry.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [f"# N23: scenario geometry and PPR mechanism (pure regime, pool 78, seed 0)", "",
             f"- causal graph per scenario: {summary['graph_events']} events, {summary['graph_edges']} edges",
             "- mean cosine to query: " + ", ".join(f"{k} {v:.3f}" for k, v in summary["mean_cos_to_query"].items()),
             f"- mean root boost {summary['b_root_mean']:.3f}, mean episodic ratio rho {summary['rho_mean']:.3f}; "
             f"(1-rho)/(rho*b) at the means = {summary['mult_lambda_at_means_bj0']:.2f}",
             "- PPR mass by event kind (mean over %d scenarios): " % n_ppr
             + ", ".join(f"{k} {v:.3f}" for k, v in summary["ppr_mass_by_event_kind"].items()),
             "- labels in PPR top-5: " + ", ".join(f"{k} {v}" for k, v in summary["ppr_top5_label_counts"].items())]
    (OUT / "RESULTS_GEOMETRY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
