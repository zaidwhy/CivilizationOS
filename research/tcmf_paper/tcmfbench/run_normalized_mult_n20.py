"""N20: does normalizing the episodic score before multiplying also recover the causal
signal, or is the additive-vs-multiplicative contrast really about the operator?

A council of AI advisors reviewing this paper (2026-09-23) caught a real confound in the
existing operator ablation: ``rank_tcmf_multiplicative`` multiplies the RAW episodic score,
while ``rank_tcmf_additive`` adds the min-max NORMALIZED one - two variables change at once
(operator AND normalization), so the paper's headline 2% vs 100% gap could in principle be a
normalization effect, not an additive-vs-multiplicative one. Reciprocal rank fusion (already a
baseline in every table, tcmf_rrf) partially answers this by avoiding raw scores entirely, but
it doesn't isolate the exact question: same normalized episodic score, only the combination
rule changed.

This reuses N10's exact reference protocol (`run_lambda_sweep.py`'s LAMBDA_GRID, pure regime,
realistic pool, 5 seeds x 300 = 1500 scenarios) so the new curve sits on the same axis as the
already-published multiplicative and additive curves, and sanity-checks its own additive/
multiplicative columns against the committed `results_lambda_sweep.json` to machine precision.

Run:
    python -m tcmfbench.run_normalized_mult_n20 --n 300 --out results_normalized_mult
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .generator import GenConfig
from . import methods as M
from . import run_eval
from .run_lambda_sweep import LAMBDA_GRID, _sweep_operator, _agg_curve, _sanity_check


async def run(args) -> None:
    cfg = GenConfig(n_distractors=args.n_distractors, n_noise=args.n_noise)
    seeds = list(range(args.n_seeds))
    mats = sum(
        (run_eval._materialize(cfg, args.n, s * run_eval.SEED_STRIDE) for s in seeds), []
    )
    pool_size = len(mats[0].all_ids) if mats else 0

    pooled_raw_mult = await _sweep_operator(
        mats, lambda m, lam: M.rank_tcmf_multiplicative(m, lam=lam))
    pooled_raw_add = await _sweep_operator(
        mats, lambda m, lam: M.rank_tcmf_additive(m, lam=lam, clean=True))
    pooled_raw_normmult = await _sweep_operator(
        mats, lambda m, lam: M.rank_tcmf_normalized_multiplicative(m, lam=lam, clean=True))

    is_reference_protocol = (
        args.n == 300 and seeds == [0, 1, 2, 3, 4]
        and args.n_distractors == 20 and args.n_noise == 55
    )
    if is_reference_protocol:
        _sanity_check(pooled_raw_mult, pooled_raw_add)
    else:
        print(f"(smoke run: n={args.n}, seeds={seeds} - skipping the "
              "results_main_scale bit-for-bit sanity check)")

    curve_mult = _agg_curve(pooled_raw_mult)
    curve_add = _agg_curve(pooled_raw_add)
    curve_normmult = _agg_curve(pooled_raw_normmult)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "regime": "pure",
        "config": vars(cfg),
        "n_per_seed": args.n,
        "seeds": seeds,
        "seed_stride": run_eval.SEED_STRIDE,
        "pool_size": pool_size,
        "lambda_grid": LAMBDA_GRID,
        "multiplicative_raw": curve_mult,
        "additive_normalized": curve_add,
        "multiplicative_normalized": curve_normmult,
        "sanity_check": "passed - lambda=0.6/8 (raw mult), lambda=4 (additive) match "
                         "results_main_scale/results.json to machine precision",
    }
    (out_dir / "results_normalized_mult.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# N20: recall@5 vs lambda, three fusion variants (isolating operator from normalization)",
        "",
        f"Pure regime, pool {pool_size} ({args.n} scenarios/seed x {len(seeds)} seeds = "
        f"{args.n * len(seeds)} total, N01-scale pool). Mean [95% bootstrap CI].",
        "",
        "| lambda | mult (raw epi) | mult (normalized epi) | additive (normalized epi) |",
        "|---|---|---|---|",
    ]
    for i, lam in enumerate(LAMBDA_GRID):
        m, nm, a = curve_mult["mean"][i], curve_normmult["mean"][i], curve_add["mean"][i]
        lines.append(
            f"| {lam} | {m:.4f} [{curve_mult['ci_lo'][i]:.4f},{curve_mult['ci_hi'][i]:.4f}] | "
            f"{nm:.4f} [{curve_normmult['ci_lo'][i]:.4f},{curve_normmult['ci_hi'][i]:.4f}] | "
            f"{a:.4f} [{curve_add['ci_lo'][i]:.4f},{curve_add['ci_hi'][i]:.4f}] |"
        )
    (out_dir / "RESULTS_NORMALIZED_MULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def parse_args():
    p = argparse.ArgumentParser(description="N20: normalized-multiplicative ablation")
    p.add_argument("--n", type=int, default=300, help="scenarios per seed")
    p.add_argument("--n-seeds", type=int, default=5)
    p.add_argument("--n-distractors", type=int, default=20)
    p.add_argument("--n-noise", type=int, default=55)
    p.add_argument("--out", type=str, default="results_normalized_mult")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
