"""N22: the theory quantities on the PURE regime at the realistic pool (the setting of the
headline results), rather than on one mixed-regime scenario per seed (results_theory).

Measures, per scenario (5 seeds x 300, pool 78, threshold 0.45, clean, favor_root=False):
  - how often a non-gold memory (distractor or noise) receives a nonzero causal boost;
  - the additive uniform lambda bound and the multiplicative required lambda for lifting the
    root cause over EVERY non-gold memory (not only distractors);
  - for F15, how often min-max normalization sends a causal-gold memory's episodic score to
    exactly 0 (the pool minimum), where normalized-multiplicative fusion can never lift it.

Run: python -m tcmfbench.run_theory_pure_n22
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import theory as T
from .generator import GenConfig, generate_many
from .run_eval import SEED_STRIDE

OUT = Path(__file__).resolve().parents[1] / "results_theory_pure"
BOOST_KW = dict(threshold=0.45, clean=True, favor_root=False)


def analyse(mat) -> dict:
    e = M._episodic_scores(mat)
    b = M._causal_boosts(mat, **BOOST_KW)
    ehat = M._minmax(e)
    gold = set(mat.gold_ids)
    root = mat.root_id
    non_gold = [i for i in mat.all_ids if i not in gold]
    dis = M.distractor_ids(mat)
    noise = [i for i in non_gold if i not in dis]
    return {
        "b_root": b[root],
        "frac_distractors_boosted": sum(b[d] > 0 for d in dis) / len(dis),
        "frac_noise_boosted": sum(b[n] > 0 for n in noise) / max(1, len(noise)),
        "max_nongold_boost": max(b[i] for i in non_gold),
        "add_required": T.additive_required_lambda(b, root, set(non_gold)),
        "mult_required": T.mult_required_lambda(e, b, root, set(non_gold)),
        "ehat_root": ehat[root],
        "any_gold_ehat_zero": any(ehat[g] == 0.0 for g in gold),
        "root_ehat_zero": ehat[root] == 0.0,
        # F15: the episodic ratio rho = e(root)/e(strongest non-gold) before and after min-max
        # normalization, and the multiplicative requirement recomputed on the normalized score.
        "rho_raw": e[root] / max(e[i] for i in non_gold),
        "rho_norm": ehat[root] / max(ehat[i] for i in non_gold),
        "normmult_required": T.mult_required_lambda(ehat, b, root, set(non_gold)),
    }


def main(n=300, seeds=(0, 1, 2, 3, 4)):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    rows = []
    for s in seeds:
        for sc in generate_many(n, cfg, base_seed=s * SEED_STRIDE):
            rows.append(analyse(M.materialize(sc, cfg.max_mem_per_citizen)))

    def arr(k):
        return np.array([r[k] for r in rows], dtype=float)

    add, mult = arr("add_required"), arr("mult_required")
    fin_add, fin_mult = add[np.isfinite(add)], mult[np.isfinite(mult)]
    summary = {
        "n": len(rows),
        "frac_scenarios_any_distractor_boosted": float(np.mean(arr("frac_distractors_boosted") > 0)),
        "mean_frac_distractors_boosted": float(arr("frac_distractors_boosted").mean()),
        "frac_scenarios_any_noise_boosted": float(np.mean(arr("frac_noise_boosted") > 0)),
        "frac_scenarios_nongold_outboosts_root": float(np.mean(arr("max_nongold_boost") >= arr("b_root"))),
        "b_root_min": float(arr("b_root").min()), "b_root_max": float(arr("b_root").max()),
        "add_required_finite_frac": float(np.isfinite(add).mean()),
        "add_required_p50": float(np.median(fin_add)), "add_required_p99": float(np.percentile(fin_add, 99)),
        "add_required_max": float(fin_add.max()),
        "frac_lambda4_clears_add_bound": float(np.mean(add < 4.0)),
        "mult_required_finite_frac": float(np.isfinite(mult).mean()),
        "mult_required_p5": float(np.percentile(fin_mult, 5)),
        "mult_required_p50": float(np.median(fin_mult)),
        "mult_required_p95": float(np.percentile(fin_mult, 95)),
        "mult_required_max": float(fin_mult.max()),
        "frac_lambda4_clears_mult_requirement": float(np.mean(mult < 4.0)),
        "frac_lambda8_clears_mult_requirement": float(np.mean(mult < 8.0)),
        "frac_root_ehat_zero": float(arr("root_ehat_zero").mean()),
        "frac_any_gold_ehat_zero": float(arr("any_gold_ehat_zero").mean()),
        "ehat_root_mean": float(arr("ehat_root").mean()),
        "rho_raw_mean": float(arr("rho_raw").mean()),
        "rho_norm_mean": float(arr("rho_norm").mean()),
        "frac_rho_norm_below_rho_raw": float(np.mean(arr("rho_norm") < arr("rho_raw"))),
        "normmult_required_p50": float(np.median(arr("normmult_required")[np.isfinite(arr("normmult_required"))])),
        "normmult_required_p95": float(np.percentile(arr("normmult_required")[np.isfinite(arr("normmult_required"))], 95)),
        "frac_normmult_needs_more_than_mult": float(np.mean(arr("normmult_required") > arr("mult_required"))),
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "results_theory_pure.json").write_text(
        json.dumps({"config": {"pool": 78, "seeds": list(seeds), "n_per_seed": n, **BOOST_KW},
                    "summary": summary}, indent=2), encoding="utf-8")
    lines = ["# N22: theory quantities on the pure regime, realistic pool (n=%d)" % len(rows), "",
             "| quantity | value |", "|---|---|"]
    lines += [f"| {k} | {v:.4f} |" if isinstance(v, float) else f"| {k} | {v} |" for k, v in summary.items()]
    (OUT / "RESULTS_THEORY_PURE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
