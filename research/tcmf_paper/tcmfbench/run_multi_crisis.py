"""N16: multi-crisis stress test.

Two or more concurrent crises sharing one memory pool and one causal graph. Reports, per
crisis (never pooled across crises, per the item's own instruction): whether causal@5 recall
holds, and whether the causal boost still discriminates - does querying crisis A leak a boost
onto crisis B's ancestor witnesses, now that they sit in the same shared graph?

Run:
    python -m tcmfbench.run_multi_crisis --n 60 --out results_multi_crisis
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .multi_crisis import MultiCrisisConfig, generate_multi_crisis, materialize_multi_crisis, \
    crisis_scoped_mat
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci

N_CRISES_GRID = (2, 3, 4, 8)
SEED = 0


def _eval_one(mat, view) -> dict:
    scoped = crisis_scoped_mat(mat, view)
    ranked = M.rank_tcmf_additive(scoped, lam=4.0, threshold=0.45, clean=True)
    boosts = M._causal_boosts(scoped, threshold=0.45, clean=True)
    other = [boosts.get(i, 0.0) for i in view.other_crises_gold_ids]
    own = [boosts.get(i, 0.0) for i in view.gold_ids]
    return {
        "recall@5": MT.recall_at_k(ranked, scoped.gold_ids, 5),
        "causal@5": MT.recall_at_k(ranked, scoped.gold_causal, 5),
        "root_rank": MT.rank_of(ranked, scoped.root_id) or (len(ranked) + 1),
        "own_boost_mean": float(np.mean(own)) if own else 0.0,
        "other_crisis_boost_max": float(max(other)) if other else 0.0,
        "other_crisis_boost_mean": float(np.mean(other)) if other else 0.0,
    }


def _agg(rows: list[dict]) -> dict:
    out = {}
    for k in rows[0]:
        vals = np.array([r[k] for r in rows], dtype=float)
        out[k] = bootstrap_ci(vals, seed=0)
    return out


def run(args) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_results = []

    for n_crises in N_CRISES_GRID:
        # n_topics must cover every crisis's surface + ancestor topics with none shared
        # (chain_len=4 -> 4 topics/crisis); scale it up for larger crisis counts.
        cfg = MultiCrisisConfig(n_crises=n_crises, n_topics=max(24, n_crises * 4 + 4))
        rows: list[dict] = []
        for i in range(args.n):
            sc, specs = generate_multi_crisis(f"mc_{n_crises}_{i}", cfg, seed=SEED + i)
            mat, views = materialize_multi_crisis(sc, specs, cfg)
            for view in views:
                rows.append(_eval_one(mat, view))
        agg = _agg(rows)
        probe_sc, _probe_specs = generate_multi_crisis(f"mc_{n_crises}_probe", cfg, seed=SEED)
        pool_size = len(M.materialize(probe_sc, cfg.max_mem_per_citizen).all_ids)
        grid_results.append({
            "n_crises": n_crises, "pool_size": pool_size,
            "n_crisis_queries": len(rows), "agg": agg,
        })
        print(f"n_crises={n_crises} pool={pool_size} n_queries={len(rows)}: "
              f"causal@5={agg['causal@5'][0]:.3f} other_boost_max={agg['other_crisis_boost_max'][0]:.4f} "
              f"[{agg['other_crisis_boost_max'][1]:.4f},{agg['other_crisis_boost_max'][2]:.4f}]")

    lines = [
        "# TCMF Benchmark: Multi-Crisis Stress Test (N16)",
        "",
        f"{args.n} scenarios per n_crises point (seed={SEED}), every crisis in every scenario "
        "queried and scored separately - per-crisis metrics, never pooled across crises. "
        "`other_crisis_boost` is the causal boost the OTHER crises' true ancestor witnesses "
        "receive when querying THIS crisis - the cross-contamination check.",
        "",
        "| n_crises | pool | n_queries | causal@5 | recall@5 | own_boost_mean | "
        "other_crisis_boost_mean | other_crisis_boost_max |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in grid_results:
        a = g["agg"]
        lines.append(
            f"| {g['n_crises']} | {g['pool_size']} | {g['n_crisis_queries']} | "
            f"{a['causal@5'][0]:.3f} [{a['causal@5'][1]:.3f},{a['causal@5'][2]:.3f}] | "
            f"{a['recall@5'][0]:.3f} | {a['own_boost_mean'][0]:.3f} | "
            f"{a['other_crisis_boost_mean'][0]:.4f} | "
            f"{a['other_crisis_boost_max'][0]:.4f} "
            f"[{a['other_crisis_boost_max'][1]:.4f},{a['other_crisis_boost_max'][2]:.4f}] |"
        )
    lines.append("")
    (out_dir / "RESULTS_MULTI_CRISIS.md").write_text("\n".join(lines), encoding="utf-8")

    def _ser(agg):
        return {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}

    (out_dir / "results_multi_crisis.json").write_text(json.dumps({
        "n": args.n, "seed": SEED, "n_crises_grid": list(N_CRISES_GRID),
        "rows": [{"n_crises": g["n_crises"], "pool_size": g["pool_size"],
                  "n_crisis_queries": g["n_crisis_queries"], "agg": _ser(g["agg"])}
                 for g in grid_results],
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {out_dir / 'RESULTS_MULTI_CRISIS.md'} and "
          f"{out_dir / 'results_multi_crisis.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N16: multi-crisis stress test")
    p.add_argument("--n", type=int, default=60, help="scenarios per n_crises grid point")
    p.add_argument("--out", type=str, default="results_multi_crisis")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
