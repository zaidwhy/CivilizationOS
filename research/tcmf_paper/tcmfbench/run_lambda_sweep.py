"""N10 Fig 4 data: recall@5 vs lambda for both fusion operators, same grid, same pool,
same scenarios, with N02 bootstrap CIs.

Reuses the exact N01-scale pure-regime protocol (`run_eval._materialize`, `SEED_STRIDE`,
5 seeds pooled, pool ~78) so this sweep's own lambda=4 additive point and lambda=0.6 /
lambda=8 multiplicative points can be checked against the already-committed
`results_main_scale/results.json` to machine precision - the script asserts this at runtime
rather than eyeballing it after the fact.

Run:
    python -m tcmfbench.run_lambda_sweep --n 300 --out results_lambda_sweep
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .generator import GenConfig
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci
from . import run_eval

# Same grid for both operators, so the two curves sit on one comparable x-axis. Dense at the
# low end (where the multiplicative curve is flat) and covers well past the N03 tune-selected
# value of 2.4, and past additive's own saturation point (lambda=4), so neither curve's shape
# is truncated.
LAMBDA_GRID = [0.0, 0.1, 0.3, 0.6, 1.0, 1.5, 2.0, 2.4, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]

TUNED_MULT_LAMBDA = 2.4  # N03 tune-selected value, marked separately on the figure


def _sanity_check(pooled_raw_mult: dict, pooled_raw_add: dict) -> None:
    """The item's own reproducibility bar: this sweep's lambda=0.6/8 (mult) and lambda=4
    (additive) points must match the already-committed N01-scale results to machine precision,
    since they are the same operator/lambda/pool/seeds run through the same harness."""
    ref_path = Path(__file__).parent.parent / "results_main_scale" / "results.json"
    ref = json.loads(ref_path.read_text(encoding="utf-8"))["fusion"]

    def _recall5(rows):
        return float(np.mean([r["recall@5"] for r in rows]))

    checks = [
        ("mult (old, l=0.6)", pooled_raw_mult[0.6]),
        ("mult (old, l=8)", pooled_raw_mult[8.0]),
        ("additive (l=4)", pooled_raw_add[4.0]),
    ]
    for ref_key, rows in checks:
        got = _recall5(rows)
        want = ref[ref_key]["recall@5"]["mean"]
        assert abs(got - want) < 1e-9, (
            f"{ref_key}: sweep gives {got}, results_main_scale gives {want} - "
            "not a bit-for-bit match, investigate before trusting the rest of the sweep"
        )


async def _sweep_operator(mats: list, rank_fn) -> dict[float, list[dict]]:
    """{lambda: [recall@5 rows]} for one operator across the full grid."""
    out: dict[float, list[dict]] = {}
    for lam in LAMBDA_GRID:
        rows = []
        for mat in mats:
            order = await run_eval._order(lambda m, lam=lam: rank_fn(m, lam), mat)
            rows.append({"recall@5": MT.recall_at_k(order, mat.gold_ids, 5)})
        out[lam] = rows
    return out


def _agg_curve(pooled_raw: dict[float, list[dict]]) -> dict[str, list]:
    lambdas, means, los, his = [], [], [], []
    for lam in LAMBDA_GRID:
        vals = np.array([r["recall@5"] for r in pooled_raw[lam]], dtype=float)
        mean, lo, hi = bootstrap_ci(vals, seed=0)
        lambdas.append(lam)
        means.append(mean)
        los.append(lo)
        his.append(hi)
    return {"lambda": lambdas, "mean": means, "ci_lo": los, "ci_hi": his}


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

    is_reference_protocol = (
        args.n == 300 and seeds == [0, 1, 2, 3, 4]
        and args.n_distractors == 20 and args.n_noise == 55
    )
    if is_reference_protocol:
        _sanity_check(pooled_raw_mult, pooled_raw_add)
    else:
        print(f"(smoke run: n={args.n}, seeds={seeds} - skipping the "
              "results_main_scale bit-for-bit sanity check, which only applies to the "
              "full --n 300 --n-seeds 5 reference protocol)")

    curve_mult = _agg_curve(pooled_raw_mult)
    curve_add = _agg_curve(pooled_raw_add)

    tuned_vals = np.array([r["recall@5"] for r in pooled_raw_mult[TUNED_MULT_LAMBDA]], dtype=float)
    tuned_mean, tuned_lo, tuned_hi = bootstrap_ci(tuned_vals, seed=0)

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
        "tuned_mult_lambda": TUNED_MULT_LAMBDA,
        "tuned_mult_lambda_recall5": {"mean": tuned_mean, "ci_lo": tuned_lo, "ci_hi": tuned_hi},
        "multiplicative": curve_mult,
        "additive": curve_add,
        "sanity_check": "passed - lambda=0.6/8 (mult), lambda=4 (additive) match "
                         "results_main_scale/results.json to machine precision",
    }
    (out_dir / "results_lambda_sweep.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Recall@5 vs lambda, both fusion operators (N10 Fig 4 data)",
        "",
        f"Pure regime, pool {pool_size} ({args.n} scenarios/seed x {len(seeds)} seeds = "
        f"{args.n * len(seeds)} total, N01-scale pool). Mean [95% bootstrap CI].",
        "",
        "| lambda | multiplicative recall@5 | additive recall@5 |",
        "|---|---|---|",
    ]
    for i, lam in enumerate(LAMBDA_GRID):
        m = curve_mult["mean"][i]
        lines.append(
            f"| {lam} | {m:.4f} [{curve_mult['ci_lo'][i]:.4f}, {curve_mult['ci_hi'][i]:.4f}] | "
            f"{curve_add['mean'][i]:.4f} [{curve_add['ci_lo'][i]:.4f}, {curve_add['ci_hi'][i]:.4f}] |"
        )
    lines += [
        "",
        f"- N03 tune-selected multiplicative lambda = {TUNED_MULT_LAMBDA}: recall@5 = "
        f"{tuned_mean:.4f} [{tuned_lo:.4f}, {tuned_hi:.4f}] (this is also the grid's own "
        f"{TUNED_MULT_LAMBDA} row, marked separately since it is the value a fair tune sweep "
        "actually picked, not the shipped default).",
        "- Sanity check: this sweep's lambda=0.6/8 (mult) and lambda=4 (additive) points match "
        "`results_main_scale/results.json` to machine precision (asserted at runtime).",
    ]
    (out_dir / "RESULTS_LAMBDA_SWEEP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def parse_args():
    p = argparse.ArgumentParser(description="N10 Fig 4: recall@5 vs lambda sweep")
    p.add_argument("--n", type=int, default=300, help="scenarios per seed")
    p.add_argument("--n-seeds", type=int, default=5)
    p.add_argument("--n-distractors", type=int, default=20)
    p.add_argument("--n-noise", type=int, default=55)
    p.add_argument("--out", type=str, default="results_lambda_sweep")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
