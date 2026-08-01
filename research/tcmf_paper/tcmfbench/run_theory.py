"""Regenerate the fusion-operator theory table: the lambda each operator REQUIRES.

Proposition 1 says the multiplicative crossing point depends on the episodic scores and so
has no bound in terms of the causal margin; Proposition 2 says the additive requirement is
bounded by 1/(b(r) - b(d)), which involves no episodic term at all. This script measures
both on real scenarios so the claim is reported from data rather than asserted.

Run:
    python -m tcmfbench.run_theory --seeds 10 --out results_theory
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import theory as T
from .mixed import MixedConfig, generate_mixed

BOOST_KW = dict(threshold=0.45, clean=True, favor_root=False)


def _fmt(x: float) -> str:
    return "unreachable" if not math.isfinite(x) else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--n-distractors", type=int, default=20)
    ap.add_argument("--n-noise", type=int, default=55)
    ap.add_argument("--shipped-lambda", type=float, default=4.0,
                    help="the lambda tcmf_add actually ships with")
    ap.add_argument("--out", type=str, default="results_theory")
    args = ap.parse_args()

    cfg = MixedConfig(n_distractors=args.n_distractors, n_noise=args.n_noise)
    rows = []
    for seed in range(1, args.seeds + 1):
        mat = M.materialize(generate_mixed(f"s{seed}", cfg, seed=seed))
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, **BOOST_KW)
        root = mat.root_id
        dis = M.distractor_ids(mat)
        rows.append({
            "seed": seed,
            "pool_size": len(mat.all_ids),
            "n_distractors": len(dis),
            "mult_required_lambda": T.mult_required_lambda(e, b, root, dis),
            "add_required_lambda": T.additive_required_lambda(b, root, dis),
            "root_episodic": e[root],
            "max_distractor_episodic": max(e[d] for d in dis),
            "root_boost": b[root],
            "max_distractor_boost": max(b[d] for d in dis),
            "n_unpromotable": len(T.unpromotable_pairs(e, b, root, dis)),
        })

    mult = [r["mult_required_lambda"] for r in rows if math.isfinite(r["mult_required_lambda"])]
    add = [r["add_required_lambda"] for r in rows if math.isfinite(r["add_required_lambda"])]
    n_unreachable = sum(1 for r in rows if not math.isfinite(r["mult_required_lambda"]))
    summary = {
        "seeds": args.seeds,
        "mult_lambda_min": min(mult), "mult_lambda_max": max(mult),
        "mult_lambda_spread": max(mult) / min(mult),
        "add_lambda_min": min(add), "add_lambda_max": max(add),
        "add_lambda_spread": max(add) / min(add),
        "n_scenarios_multiplicative_cannot_solve": n_unreachable,
        "total_distractor_pairs": sum(r["n_distractors"] for r in rows),
        "total_unpromotable_pairs": sum(r["n_unpromotable"] for r in rows),
        "shipped_lambda": args.shipped_lambda,
        "shipped_lambda_clears_additive_bound_on_all_seeds": all(
            r["add_required_lambda"] < args.shipped_lambda for r in rows
            if math.isfinite(r["add_required_lambda"])
        ),
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results_theory.json").write_text(
        json.dumps({"config": vars(args), "rows": rows, "summary": summary}, indent=2),
        encoding="utf-8")

    lines = [
        "# Required lambda per fusion operator",
        "",
        f"Pool {rows[0]['pool_size']} candidates, {rows[0]['n_distractors']} distractors, "
        f"{args.seeds} seeds. `clean=True, favor_root=False, threshold=0.45`.",
        "",
        "| seed | mult needs | additive needs (uniform bound) | e(root) | max e(distractor) |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['seed']} | {_fmt(r['mult_required_lambda'])} | "
            f"{_fmt(r['add_required_lambda'])} | {r['root_episodic']:.3f} | "
            f"{r['max_distractor_episodic']:.3f} |")
    lines += [
        "",
        f"- Multiplicative requirement spans {summary['mult_lambda_min']:.2f} to "
        f"{summary['mult_lambda_max']:.2f} ({summary['mult_lambda_spread']:.1f}x), plus "
        f"{n_unreachable} scenario(s) no lambda solves.",
        f"- Additive requirement spans {summary['add_lambda_min']:.2f} to "
        f"{summary['add_lambda_max']:.2f} ({summary['add_lambda_spread']:.2f}x).",
        f"- Unpromotable root/distractor pairs: "
        f"{summary['total_unpromotable_pairs']} of {summary['total_distractor_pairs']}.",
        f"- The shipped lambda = {args.shipped_lambda} clears the additive bound on every "
        f"solvable seed: {summary['shipped_lambda_clears_additive_bound_on_all_seeds']}.",
    ]
    (out / "RESULTS_THEORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
