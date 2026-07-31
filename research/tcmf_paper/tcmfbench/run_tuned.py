"""N03: held-out tuning split.

Lambda (tcmf_add/tcmf_mult), RRF's c, causal_only's tau, and graph_ppr's alpha were all picked
with the eval set in view - a straight "tuned on test" objection. This script fixes that:
scenario seeds are partitioned into a TUNE split (40%) and a disjoint TEST split (60%); every
swept hyperparameter is selected using TUNE data only, then every headline number is reported
on TEST with the tune-selected values. The TEST split is never inspected while selecting.

    python -m tcmfbench.run_tuned --regime pure  --out results_main_tuned
    python -m tcmfbench.run_tuned --regime mixed --out results_mixed_tuned
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .generator import GenConfig
from .mixed import MixedConfig
from . import methods as M
from . import metrics as MT
from . import run_eval
from . import run_mixed

# Fixed, disjoint 40/60 split of the 5 base seeds N01/N02 already established as the
# realistic-pool protocol (0..4, each offset by SEED_STRIDE). "Fixed" per the queue spec:
# this split is not re-drawn per run, so a later night cannot quietly re-partition it to get
# a better-looking tune score.
SEED_STRIDE = run_eval.SEED_STRIDE  # == run_mixed.SEED_STRIDE, asserted in test_n03_tune_split
TUNE_SEEDS = (0, 1)        # 2/5 = 40%
TEST_SEEDS = (2, 3, 4)     # 3/5 = 60%

# Standing rule: "every operator gets an equal sweep budget - state the budget." Budget = 5
# candidate values per operator, one hyperparameter swept at a time (others held at the main
# comparison table's own default), selected by mean recall@5 on the TUNE split only.
SWEEP_BUDGET = 5

GRIDS = {
    "tcmf_add_lambda":  [0.5, 1.0, 2.0, 4.0, 8.0],   # same grid run_eval's lambda ablation uses
    "tcmf_mult_lambda": [0.1, 0.3, 0.6, 1.2, 2.4],   # centered on the shipped-old default 0.6
    "rrf_c":            [2.0, 5.0, 10.0, 20.0, 40.0],  # centered on the RRF default c=10
    "causal_only_tau":  [0.30, 0.45, 0.60, 0.75, 0.90],
    "graph_ppr_alpha":  [0.50, 0.65, 0.75, 0.85, 0.95],
}
for _name, _grid in GRIDS.items():
    assert len(_grid) == SWEEP_BUDGET, f"{_name} grid must have exactly {SWEEP_BUDGET} candidates"

SELECTION_METRIC = "recall@5"  # the paper's standing headline metric (also _COLS[1] in both
                                # run_eval.py and run_mixed.py, and the default metric
                                # _significance_table uses) - used for every operator so the
                                # selection rule itself is not tuned per operator.


def select_best(scores: dict[float, float]) -> float:
    """Argmax by score; ties broken toward the smallest candidate value (deterministic, and
    biases toward the cheaper/more-conservative hyperparameter rather than an arbitrary one)."""
    return max(scores, key=lambda v: (scores[v], -v))


def _candidate_fns() -> dict[str, dict[float, object]]:
    """{operator_key: {candidate_value: method_fn}}. Method signatures are identical in the
    pure and mixed regimes (both consume a `Materialized`), so one factory covers both."""
    return {
        "tcmf_add_lambda": {
            v: (lambda m, v=v: M.rank_tcmf_additive(m, lam=v, clean=True))
            for v in GRIDS["tcmf_add_lambda"]
        },
        "tcmf_mult_lambda": {
            v: (lambda m, v=v: M.rank_tcmf_multiplicative(m, lam=v))
            for v in GRIDS["tcmf_mult_lambda"]
        },
        "rrf_c": {
            v: (lambda m, v=v: M.rank_tcmf_rrf(m, c=v, clean=True))
            for v in GRIDS["rrf_c"]
        },
        "causal_only_tau": {
            v: (lambda m, v=v: M.rank_causal_only(m, threshold=v, clean=True))
            for v in GRIDS["causal_only_tau"]
        },
        "graph_ppr_alpha": {
            v: (lambda m, v=v: M.rank_graph_ppr(m, alpha=v))
            for v in GRIDS["graph_ppr_alpha"]
        },
    }


def _tuned_pure_methods(sel: dict[str, float]) -> dict:
    m = dict(run_eval.main_methods())
    m["causal_only"] = lambda mm: M.rank_causal_only(mm, threshold=sel["causal_only_tau"], clean=True)
    m["graph_ppr"] = lambda mm: M.rank_graph_ppr(mm, alpha=sel["graph_ppr_alpha"])
    m["tcmf_mult"] = lambda mm: M.rank_tcmf_multiplicative(mm, lam=sel["tcmf_mult_lambda"])
    m["tcmf_add"] = lambda mm: M.rank_tcmf_additive(mm, lam=sel["tcmf_add_lambda"], clean=True)
    m["tcmf_rrf"] = lambda mm: M.rank_tcmf_rrf(mm, c=sel["rrf_c"], clean=True)
    return m


def _tuned_mixed_methods(sel: dict[str, float]) -> dict:
    m = dict(run_mixed._methods())
    m["causal_only"] = lambda mm: M.rank_causal_only(mm, threshold=sel["causal_only_tau"], clean=True)
    m["graph_ppr"] = lambda mm: M.rank_graph_ppr(mm, alpha=sel["graph_ppr_alpha"])
    m["tcmf_mult"] = lambda mm: M.rank_tcmf_multiplicative(mm, lam=sel["tcmf_mult_lambda"])
    m["tcmf_add"] = lambda mm: M.rank_tcmf_additive(mm, lam=sel["tcmf_add_lambda"], clean=True)
    m["tcmf_rrf"] = lambda mm: M.rank_tcmf_rrf(mm, c=sel["rrf_c"], clean=True)
    return m


def _pool_mats(regime: str, cfg, n: int, seeds: tuple[int, ...]) -> list:
    if regime == "pure":
        return sum((run_eval._materialize(cfg, n, s * SEED_STRIDE) for s in seeds), [])
    return sum((run_mixed._mats(cfg, n, s * SEED_STRIDE) for s in seeds), [])


async def _sweep(mats_tune: list) -> tuple[dict[str, float], dict[str, dict[float, float]]]:
    """Sweep every operator's grid on TUNE data only. Returns (selected, tune_scores)."""
    selected: dict[str, float] = {}
    tune_scores: dict[str, dict[float, float]] = {}
    for op_key, grid_fns in _candidate_fns().items():
        scores: dict[float, float] = {}
        for v, fn in grid_fns.items():
            vals = []
            for mat in mats_tune:
                order = await run_eval._order(fn, mat)
                vals.append(MT.recall_at_k(order, mat.gold_ids, 5))
            scores[v] = float(np.mean(vals))
        tune_scores[op_key] = scores
        selected[op_key] = select_best(scores)
    return selected, tune_scores


def _sweep_table(tune_scores: dict[str, dict[float, float]], selected: dict[str, float]) -> str:
    lines = [
        f"### N03 tune-set hyperparameter sweep (recall@5, mean over TUNE split only, "
        f"budget={SWEEP_BUDGET} candidates/operator)",
        "",
        "| operator | candidate | tune recall@5 | selected |",
        "|---|---|---|---|",
    ]
    for op_key, scores in tune_scores.items():
        best = selected[op_key]
        for v, s in scores.items():
            mark = " **<-selected**" if v == best else ""
            lines.append(f"| {op_key} | {v} | {s:.4f}{mark} | |")
    lines.append("")
    lines.append("| operator | selected value |")
    lines.append("|---|---|")
    for op_key, v in selected.items():
        lines.append(f"| {op_key} | {v} |")
    return "\n".join(lines)


def _load_n01_recall10(regime: str) -> dict[str, float] | None:
    """Recall@10 means from the already-committed N01 realistic-pool run, for the ordering
    check the queue's Verify section asks for. Read from the committed JSON, not re-derived."""
    path = (Path(__file__).parent.parent /
            ("results_main_scale/results.json" if regime == "pure"
             else "results_mixed_scale/results_mixed.json"))
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: agg["recall@10"]["mean"] for name, agg in data["main"].items()}


def _ordering_check(regime: str, order: list[str], test_main: dict) -> str:
    n01 = _load_n01_recall10(regime)
    test_recall10 = {name: test_main[name]["recall@10"][0] for name in order if name in test_main}
    test_rank = sorted(test_recall10, key=lambda n: test_recall10[n], reverse=True)
    lines = [
        "### Headline-ordering check vs N01 (recall@10, descending)",
        "",
    ]
    if n01 is None:
        lines.append("N01 result file not found - ordering comparison skipped.")
        return "\n".join(lines)
    n01_recall10 = {name: n01[name] for name in order if name in n01}
    n01_rank = sorted(n01_recall10, key=lambda n: n01_recall10[n], reverse=True)
    lines += [
        "| rank | N01 (pooled, all 5 seeds, untuned lambda/tau) | N03 test-only "
        "(3 seeds, tune-selected lambda/tau) |",
        "|---|---|---|",
    ]
    for i in range(max(len(n01_rank), len(test_rank))):
        a = n01_rank[i] if i < len(n01_rank) else ""
        b = test_rank[i] if i < len(test_rank) else ""
        lines.append(f"| {i + 1} | {a} | {b} |")
    lines.append("")
    if n01_rank == test_rank:
        lines.append("Ordering UNCHANGED from N01.")
    else:
        lines.append(
            "Ordering CHANGED from N01 (see ranks above) - this is the honest N03 result, "
            "not smoothed over."
        )
    return "\n".join(lines)


async def run_regime(regime: str, args) -> None:
    overrides = {}
    if args.n_distractors is not None:
        overrides["n_distractors"] = args.n_distractors
    if args.n_noise is not None:
        overrides["n_noise"] = args.n_noise
    n = args.n

    cfg = GenConfig(**overrides) if regime == "pure" else MixedConfig(**overrides)
    mats_tune = _pool_mats(regime, cfg, n, TUNE_SEEDS)
    mats_test = _pool_mats(regime, cfg, n, TEST_SEEDS)
    pool_size = len(mats_tune[0].all_ids) if mats_tune else 0

    selected, tune_scores = await _sweep(mats_tune)
    sweep_md = _sweep_table(tune_scores, selected)

    if regime == "pure":
        order = run_eval.MAIN_ORDER
        tuned_methods = _tuned_pure_methods(selected)
        pooled_raw = await run_eval._eval_methods_raw(mats_test, tuned_methods)
        run_eval._verify_null_contrast_is_null(pooled_raw, ref="tcmf_add")
        main = run_eval._eval_methods_agg(pooled_raw)
        main_md = run_eval._table(
            "Main comparison (TEST split only, tune-selected hyperparameters)", main, order)
        significance = run_eval._significance_table(pooled_raw, order, ref="tcmf_add")
    else:
        order = run_mixed.ORDER
        tuned_methods = _tuned_mixed_methods(selected)
        pooled_raw = await run_mixed._eval_raw(mats_test, tuned_methods)
        run_mixed._verify_null_contrast_is_null(pooled_raw, ref="tcmf_add")
        main = run_mixed._eval_agg(pooled_raw)
        main_md = run_mixed._table(
            "Main comparison (TEST split only, tune-selected hyperparameters)", main, order)
        significance = run_mixed._significance_table(
            pooled_raw, order, ref="tcmf_add", metrics=("recall@5", "recall@10", "root_rank"))

    ordering_md = _ordering_check(regime, order, main)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [
        f"# TCMF Benchmark: {regime} regime, held-out tuning split (N03)",
        "",
        f"tune seeds: {TUNE_SEEDS} (n={n} each, {n * len(TUNE_SEEDS)} scenarios) | "
        f"test seeds: {TEST_SEEDS} (n={n} each, {n * len(TEST_SEEDS)} scenarios) | "
        f"stride: {SEED_STRIDE} | pool/scenario: {pool_size} | "
        f"selection metric: {SELECTION_METRIC} (TUNE only)",
        "",
        "Every hyperparameter below (tcmf_add lambda, tcmf_mult lambda, RRF c, causal_only "
        "tau, graph_ppr alpha) is selected using ONLY the tune split, then every table below "
        "is computed on the disjoint test split with the selected values plugged in. The test "
        "split was never inspected while selecting.",
        "",
        sweep_md, "",
        main_md, "",
        significance, "",
        ordering_md, "",
    ]
    (out_dir / "RESULTS_TUNED.md").write_text("\n".join(md), encoding="utf-8")

    def _ser(d):
        return {nm: {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}
                for nm, agg in d.items()}

    (out_dir / "results_tuned.json").write_text(json.dumps({
        "regime": regime, "config": vars(cfg), "n": n,
        "tune_seeds": list(TUNE_SEEDS), "test_seeds": list(TEST_SEEDS),
        "seed_stride": SEED_STRIDE, "sweep_budget": SWEEP_BUDGET,
        "selection_metric": SELECTION_METRIC, "pool_size": pool_size,
        "tune_scores": tune_scores, "selected": selected,
        "test_main": _ser(main),
    }, indent=2), encoding="utf-8")

    print(sweep_md)
    print("\n" + main_md.replace("### ", "== "))
    print("\n" + significance.replace("### ", "== "))
    print("\n" + ordering_md.replace("### ", "== "))
    print(f"\nWrote {out_dir / 'RESULTS_TUNED.md'} and {out_dir / 'results_tuned.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N03: held-out tuning split")
    p.add_argument("--regime", choices=("pure", "mixed"), default="pure")
    p.add_argument("--n", type=int, default=300, help="scenarios per seed")
    p.add_argument("--out", type=str, default="results_tuned")
    p.add_argument("--n-distractors", type=int, default=20,
                    help="default 20 = N01's realistic-pool value; tuning must happen at the "
                         "realistic pool, not the old small one")
    p.add_argument("--n-noise", type=int, default=55,
                    help="default 55 = N01's realistic-pool value")
    return p.parse_args()


if __name__ == "__main__":
    _args = parse_args()
    asyncio.run(run_regime(_args.regime, _args))
