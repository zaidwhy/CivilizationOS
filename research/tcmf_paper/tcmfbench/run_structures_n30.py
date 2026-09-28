"""N30: does the regime picture hold beyond the four-event chain, and where do leaked pairs land?

A. Graph families (``structures.py``): chains of 3, 4 and 6 events, a diamond, two independent
   roots, a branching tree and a side cause joining mid-chain. Each under three conditions:
   clean, an on-topic leak (a false cause of the crisis written on the crisis topic, every
   scenario) and clutter (16 background events, 4 false edges into the chain). Both depth
   weightings. BFS depth cap 8, so the six-event chain's root (depth 5) is reachable.
   Per family: recall@5 for additive lambda=4, multiplicative lambda=16 (tuned on the four-event
   chain), the best multiplicative weight on the 12-value grid and both limits (oracle), the causal
   score alone; and, on clean graphs, the weight each operator needs for the root to outrank every
   non-gold memory (Propositions 1-2), with the share of scenarios where lambda=4 / lambda=16 suffice.

B. Pair map. Every leaked pair (i causal-gold, j non-gold, b_j > 0) placed at
   rho = e_i/e_j and beta = b_j/b_i. The propositions split this plane by two lines: in the limit,
   multiplication orders a pair correctly iff rho > beta, addition iff beta < 1. Recorded for the
   on-topic leak and for clutter on the four-event chain, proximate weights.

    python -m tcmfbench.run_structures_n30
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .clutter import ClutterConfig, add_clutter_synthetic
from .mixed import MixedConfig
from .run_eval import SEED_STRIDE
from .structures import FAMILIES, generate_family

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_structures_n30"
GRID = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
SEEDS, PER_SEED = 3, 200
BFS_CAP = 8


def _build(family, cond, s, i):
    seed = s * SEED_STRIDE + i
    mcfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0 if cond == "onleak" else 0.0)
    sc = generate_family(f"s{i:04d}", family, mcfg, seed)
    if cond == "clutter":
        sc = add_clutter_synthetic(sc, mcfg, ClutterConfig(n_background=16, n_false_edges=4), seed)
    return M.materialize(sc, mcfg.max_mem_per_citizen)


def _rank(ids, score, tie=None):
    order = np.lexsort((tie, score))[::-1] if tie is not None else np.argsort(-score, kind="stable")
    return [ids[k] for k in order]


def _needed(A, B):
    """Smallest lambda >= 0 with A + lambda*B > 0 for every pair, inf if none (upper caps ignored:
    on clean graphs B < 0 with A > 0 does not occur for the root)."""
    lo = 0.0
    for a, b in zip(A, B):
        if a > 0:
            continue
        if b <= 0:
            return float("inf")
        lo = max(lo, -a / b)
    return lo


def _scenario(mat, fr, pairs_out=None):
    ids = list(mat.all_ids)
    e_d = M._episodic_scores(mat)
    b_d = M._causal_boosts(mat, 0.45, clean=True, favor_root=fr, bfs_depth_cap=BFS_CAP)
    e = np.array([e_d[i] for i in ids])
    eh_d = M._minmax(e_d)
    eh = np.array([eh_d[i] for i in ids])
    b = np.array([b_d[i] for i in ids])

    def r5(rk):
        return MT.recall_at_k(rk, mat.gold_ids, 5)

    row = {"add_l4": r5(_rank(ids, eh + 4 * b)), "mult_l16": r5(_rank(ids, e * (1 + 16 * b))),
           "causal": r5(_rank(ids, b))}
    mult = [r5(_rank(ids, e * (1 + l * b))) for l in GRID] + [r5(_rank(ids, eh * (1 + l * b))) for l in GRID]
    mult += [r5(_rank(ids, e * b, tie=e)), r5(_rank(ids, eh * b, tie=eh))]
    row["mult_grid"] = mult

    r = ids.index(mat.root_id)
    others = [j for j in range(len(ids)) if ids[j] not in mat.gold_ids]
    row["need_mult"] = _needed([e[r] - e[j] for j in others], [e[r] * b[r] - e[j] * b[j] for j in others])
    row["need_add"] = _needed([eh[r] - eh[j] for j in others], [b[r] - b[j] for j in others])

    if pairs_out is not None:
        for gi in mat.gold_causal:
            a = ids.index(gi)
            if b[a] <= 0:
                continue
            for j in others:
                if b[j] > 0:
                    pairs_out.append((float(e[a] / e[j]), float(b[j] / b[a])))
    return row


def _summ(rows):
    grid = np.mean([r["mult_grid"] for r in rows], axis=0)
    nm = np.array([r["need_mult"] for r in rows])
    na = np.array([r["need_add"] for r in rows])

    def med(x):
        f = x[np.isfinite(x)]
        return float(np.median(f)) if len(f) else None

    return {
        "n": len(rows),
        "add_l4": float(np.mean([r["add_l4"] for r in rows])),
        "mult_l16": float(np.mean([r["mult_l16"] for r in rows])),
        "best_mult": float(grid.max()),
        "causal": float(np.mean([r["causal"] for r in rows])),
        "need_mult_median": med(nm), "need_add_median": med(na),
        "need_mult_p95": float(np.percentile(nm, 95)) if np.isfinite(np.percentile(nm, 95)) else None,
        "need_add_p95": float(np.percentile(na, 95)) if np.isfinite(np.percentile(na, 95)) else None,
        "frac_add4_suffices": float(np.mean(na < 4)),
        "frac_mult16_suffices": float(np.mean(nm < 16)),
        "frac_unreachable_mult": float(np.mean(~np.isfinite(nm))),
        "frac_unreachable_add": float(np.mean(~np.isfinite(na))),
    }


def _regions(pairs):
    p = np.array(pairs)
    rho, beta = p[:, 0], p[:, 1]
    tot = len(p)
    return {
        "n_pairs": tot,
        "frac_rho_lt_1": float(np.mean(rho < 1)),
        "mult_only_wrong": float(np.mean((beta < 1) & (rho <= beta))),   # Prop 1a
        "add_only_wrong": float(np.mean((beta > 1) & (rho > beta))),     # Prop 3
        "both_wrong": float(np.mean((beta >= 1) & (rho <= beta))),
        "both_right": float(np.mean((beta < 1) & (rho > beta))),
        "median_rho": float(np.median(rho)), "median_beta": float(np.median(beta)),
    }


def main():
    OUT.mkdir(exist_ok=True)
    res = {"grid": GRID, "families": {}, "pairs": {}}
    rng = np.random.default_rng(30)
    for family in FAMILIES:
        for cond in ("clean", "onleak", "clutter"):
            mats = [_build(family, cond, s, i) for s in range(SEEDS) for i in range(PER_SEED)]
            for fr, tag in ((False, "prox"), (True, "root")):
                collect = [] if (family == "chain4" and cond != "clean" and tag == "prox") else None
                rows = [_scenario(m, fr, collect) for m in mats]
                v = _summ(rows)
                res["families"][f"{family}_{cond}_{tag}"] = v
                if collect is not None:
                    reg = _regions(collect)
                    keep = rng.permutation(len(collect))[:4000]
                    res["pairs"][cond] = {"regions": reg, "sample": [collect[k] for k in keep]}
                print(f"{family:10s} {cond:7s} {tag} add4={v['add_l4']:.3f} mult16={v['mult_l16']:.3f} "
                      f"best={v['best_mult']:.3f} causal={v['causal']:.3f} "
                      f"need add/mult={v['need_add_median']}/{v['need_mult_median']} "
                      f"add4ok={v['frac_add4_suffices']:.2f} mult16ok={v['frac_mult16_suffices']:.2f}", flush=True)
        (OUT / "results_structures_n30.json").write_text(json.dumps(res), encoding="utf-8")
    lines = ["# N30: graph families and the leaked-pair map", "",
             "## A. Recall@5 (all gold), mixed regime pool 80, n=600 per row", "",
             "| family | condition | weights | add l=4 | mult l=16 | best mult (oracle) | causal | "
             "clean: add need median | clean: mult need median | add l=4 suffices | mult l=16 suffices |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["families"].items():
        fam, cond, tag = k.rsplit("_", 2)
        f = lambda x: "-" if x is None else f"{x:.2f}"
        lines.append(f"| {fam} | {cond} | {tag} | {v['add_l4']:.3f} | {v['mult_l16']:.3f} | {v['best_mult']:.3f} | "
                     f"{v['causal']:.3f} | {f(v['need_add_median'])} | {f(v['need_mult_median'])} | "
                     f"{v['frac_add4_suffices']:.2f} | {v['frac_mult16_suffices']:.2f} |")
    lines += ["", "## B. Leaked pairs (four-event chain, proximate weights)", "",
              "| leak | pairs | rho<1 | mult-only wrong (Prop 1a) | add-only wrong (Prop 3) | both wrong | both right | median rho | median beta |",
              "|---|---|---|---|---|---|---|---|---|"]
    for cond, d in res["pairs"].items():
        r = d["regions"]
        lines.append(f"| {cond} | {r['n_pairs']} | {r['frac_rho_lt_1']:.2f} | {r['mult_only_wrong']:.2f} | "
                     f"{r['add_only_wrong']:.2f} | {r['both_wrong']:.2f} | {r['both_right']:.2f} | "
                     f"{r['median_rho']:.2f} | {r['median_beta']:.2f} |")
    (OUT / "RESULTS_STRUCTURES_N30.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
