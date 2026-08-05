"""N07: additional retrieval baselines (MMR, BM25, summary-buffer, community-summary,
extract-and-consolidate), evaluated under the N03 held-out tune/test protocol at the N01
realistic pool.

Each is a reimplementable *mechanism*, not a system reimplementation - named "X-style
mechanism" in code and prose, the same correction already applied to graph_ppr/HippoRAG:
  - MMR                  the standard diversity re-ranker
  - BM25 lexical          tests whether the effect is a dense-embedding artifact
  - summary_buffer        MemGPT-style recent-window + paged archival summary
  - community_summary     GraphRAG-style cluster-then-retrieve-by-summary
  - extract_consolidate   Mem0-style dedupe/merge before ranking

The 10 pre-existing methods keep the hyperparameters N03 already selected on the TUNE split
(loaded from the committed results_main_tuned/results_mixed_tuned JSON, not re-derived - they
are deterministic given the same seeds/grids, so re-sweeping them would only reproduce the
same numbers at the cost of runtime). Only the 5 new baselines' single hyperparameter each is
swept fresh here, on the SAME fixed TUNE split, with the SAME equal 5-candidate budget N03
established - "run under the N03 protocol with equal tuning budget," per the queue item.

    python -m tcmfbench.run_baselines --regime pure  --out results_baselines_pure
    python -m tcmfbench.run_baselines --regime mixed --out results_baselines_mixed
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
from . import run_tuned
from .stats import bootstrap_ci, holm_bonferroni, wilcoxon_signed_rank

SEED_STRIDE = run_tuned.SEED_STRIDE
TUNE_SEEDS = run_tuned.TUNE_SEEDS
TEST_SEEDS = run_tuned.TEST_SEEDS
SWEEP_BUDGET = run_tuned.SWEEP_BUDGET  # same equal-budget-per-operator contract as N03
SELECTION_METRIC = run_tuned.SELECTION_METRIC  # recall@5, same as every N03-swept operator

NEW_NAMES = ["mmr", "bm25", "summary_buffer", "community_summary", "extract_consolidate"]

GRIDS_NEW = {
    "mmr_lambda":            [0.1, 0.3, 0.5, 0.7, 0.9],
    "bm25_k1":                [0.5, 1.0, 1.5, 2.0, 2.5],
    "summary_buffer_window":  [5, 10, 20, 40, 60],
    "community_n":            [2, 4, 6, 8, 12],
    "consolidate_threshold":  [0.80, 0.85, 0.90, 0.95, 0.98],
}
for _name, _grid in GRIDS_NEW.items():
    assert len(_grid) == SWEEP_BUDGET, f"{_name} grid must have exactly {SWEEP_BUDGET} candidates"


def _candidate_fns_new() -> dict[str, dict[float, object]]:
    return {
        "mmr_lambda": {
            v: (lambda m, v=v: M.rank_mmr(m, mmr_lambda=v)) for v in GRIDS_NEW["mmr_lambda"]
        },
        "bm25_k1": {
            v: (lambda m, v=v: M.rank_bm25(m, k1=v)) for v in GRIDS_NEW["bm25_k1"]
        },
        "summary_buffer_window": {
            v: (lambda m, v=v: M.rank_summary_buffer(m, recent_window=int(v)))
            for v in GRIDS_NEW["summary_buffer_window"]
        },
        "community_n": {
            v: (lambda m, v=v: M.rank_community_summary(m, n_communities=int(v), seed=0))
            for v in GRIDS_NEW["community_n"]
        },
        "consolidate_threshold": {
            v: (lambda m, v=v: M.rank_extract_consolidate(m, dedup_threshold=v))
            for v in GRIDS_NEW["consolidate_threshold"]
        },
    }


async def _sweep_new(mats_tune: list) -> tuple[dict[str, float], dict[str, dict[float, float]]]:
    """Sweep each new baseline's grid on TUNE data only, selecting by mean recall@5 - the
    identical selection rule and tie-break N03 used for the 5 pre-existing swept operators."""
    selected: dict[str, float] = {}
    tune_scores: dict[str, dict[float, float]] = {}
    for op_key, grid_fns in _candidate_fns_new().items():
        scores: dict[float, float] = {}
        for v, fn in grid_fns.items():
            vals = []
            for mat in mats_tune:
                order = await run_eval._order(fn, mat)
                vals.append(MT.recall_at_k(order, mat.gold_ids, 5))
            scores[v] = float(np.mean(vals))
        tune_scores[op_key] = scores
        selected[op_key] = run_tuned.select_best(scores)
    return selected, tune_scores


def _sweep_table(tune_scores: dict[str, dict[float, float]], selected: dict[str, float]) -> str:
    lines = [
        f"### N07 tune-set hyperparameter sweep for the 5 new baselines (recall@5, mean over "
        f"TUNE split only, budget={SWEEP_BUDGET} candidates/operator - same protocol N03 used)",
        "", "| operator | candidate | tune recall@5 | selected |", "|---|---|---|---|",
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


def _load_n03_selected(regime: str) -> dict[str, float]:
    """The already-committed N03 tune-selected hyperparameters for the 10 pre-existing
    methods, loaded (not re-derived) from the committed results_*_tuned/results_tuned.json -
    they are deterministic given the same seeds/grids N03 used, so re-sweeping here would only
    reproduce the identical numbers at extra runtime cost."""
    path = (Path(__file__).parent.parent /
            (f"results_{'main' if regime == 'pure' else 'mixed'}_tuned/results_tuned.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["selected"]


def _new_tuned_methods(sel_new: dict[str, float]) -> dict:
    return {
        "mmr":                lambda m: M.rank_mmr(m, mmr_lambda=sel_new["mmr_lambda"]),
        "bm25":                lambda m: M.rank_bm25(m, k1=sel_new["bm25_k1"]),
        "summary_buffer":      lambda m: M.rank_summary_buffer(
            m, recent_window=int(sel_new["summary_buffer_window"])),
        "community_summary":   lambda m: M.rank_community_summary(
            m, n_communities=int(sel_new["community_n"]), seed=0),
        "extract_consolidate": lambda m: M.rank_extract_consolidate(
            m, dedup_threshold=sel_new["consolidate_threshold"]),
    }


def beats_random(main: dict, order_new: list[str], higher_is_better: dict[str, bool]) -> dict:
    """{name: [metrics where it beats random]}. NOT a hard assertion: the queue item's own
    verify text ('a baseline that cannot [beat random on anything] is misimplemented, not
    weak') is a useful PRIOR for catching bugs, but it is not infallible, and this benchmark's
    pure regime is deliberately adversarial to anything similarity-adjacent (F1: semantic_rag
    itself gets recall@5=0.00 there). A baseline landing at zero wins gets investigated by hand
    (see the night log) before being called a bug versus a real, reportable property of the
    mechanism on this benchmark - forcing a pass here would hide exactly the kind of honest
    negative result the queue exists to surface."""
    rand = main["random"]
    out = {}
    for name in order_new:
        agg = main[name]
        wins = []
        for metric, better_high in higher_is_better.items():
            r_mean, m_mean = rand[metric][0], agg[metric][0]
            if (m_mean > r_mean) if better_high else (m_mean < r_mean):
                wins.append(metric)
        out[name] = wins
    return out


def _verify_md(wins_by_name: dict[str, list[str]], regime: str) -> str:
    lines = [f"### N07 verify ({regime} regime): does each new baseline beat `random` on at "
             "least one metric?", ""]
    for name, wins in wins_by_name.items():
        if wins:
            lines.append(f"- `{name}` beats random on: {', '.join(wins)}")
        else:
            lines.append(f"- `{name}` beats random on NO metric - see NIGHT_LOG.md for the "
                          f"mechanistic investigation of why (bug vs. real benchmark property)")
    return "\n".join(lines)


async def run_regime(regime: str, args) -> None:
    overrides = {}
    if args.n_distractors is not None:
        overrides["n_distractors"] = args.n_distractors
    if args.n_noise is not None:
        overrides["n_noise"] = args.n_noise
    n = args.n

    cfg = GenConfig(**overrides) if regime == "pure" else MixedConfig(**overrides)
    mats_tune = run_tuned._pool_mats(regime, cfg, n, TUNE_SEEDS)
    mats_test = run_tuned._pool_mats(regime, cfg, n, TEST_SEEDS)
    pool_size = len(mats_tune[0].all_ids) if mats_tune else 0

    sel_old = _load_n03_selected(regime)
    sel_new, tune_scores_new = await _sweep_new(mats_tune)
    sweep_md = _sweep_table(tune_scores_new, sel_new)
    new_methods = _new_tuned_methods(sel_new)

    if regime == "pure":
        old_methods = run_tuned._tuned_pure_methods(sel_old)  # already includes "random"
        methods = {**old_methods, **new_methods}
        order = run_eval.MAIN_ORDER + NEW_NAMES
        pooled_raw = await run_eval._eval_methods_raw(mats_test, methods)
        run_eval._verify_null_contrast_is_null(pooled_raw, ref="tcmf_add")
        main = run_eval._eval_methods_agg(pooled_raw)
        main_md = run_eval._table(
            "Main comparison + N07 baselines (TEST split, N03-tuned old / N07-tuned new)",
            main, order)
        significance = run_eval._significance_table(pooled_raw, order, ref="tcmf_add")
        higher_is_better = {c: (c != "root_rank") for c in run_eval._COLS}
    else:
        old_methods = dict(run_tuned._tuned_mixed_methods(sel_old))
        old_methods["random"] = lambda m: M.rank_random(m, seed=1234)  # not in run_mixed's
        methods = {**old_methods, **new_methods}
        order = ["random"] + run_mixed.ORDER + NEW_NAMES
        pooled_raw = await run_mixed._eval_raw(mats_test, methods)
        run_mixed._verify_null_contrast_is_null(pooled_raw, ref="tcmf_add")
        main = run_mixed._eval_agg(pooled_raw)
        main_md = run_mixed._table(
            "Main comparison + N07 baselines (TEST split, N03-tuned old / N07-tuned new)",
            main, order)
        significance = run_mixed._significance_table(
            pooled_raw, order, ref="tcmf_add", metrics=("recall@5", "recall@10", "root_rank"))
        higher_is_better = {c: (c != "root_rank") for c in run_mixed._COLS}

    wins_by_name = beats_random(main, NEW_NAMES, higher_is_better)
    verify_md = _verify_md(wins_by_name, regime)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [
        f"# TCMF Benchmark: {regime} regime, N07 additional retrieval baselines",
        "",
        f"tune seeds: {TUNE_SEEDS} (n={n} each) | test seeds: {TEST_SEEDS} (n={n} each) | "
        f"stride: {SEED_STRIDE} | pool/scenario: {pool_size} | "
        f"pre-existing-method hyperparameters: N03-tuned (loaded from "
        f"results_{'main' if regime == 'pure' else 'mixed'}_tuned, not re-derived) | "
        f"new-baseline hyperparameters: swept here on TUNE only, "
        f"budget={SWEEP_BUDGET}/operator, selection metric {SELECTION_METRIC}",
        "",
        "New baselines are reimplementable *mechanisms*, not system reimplementations: `mmr` "
        "(maximal marginal relevance), `bm25` (lexical, no embeddings), `summary_buffer` "
        "(MemGPT-style recent window + paged archival summary), `community_summary` "
        "(GraphRAG-style cluster-then-retrieve), `extract_consolidate` (Mem0-style dedupe/"
        "merge before ranking). All 5 evaluated on the TEST split only.",
        "",
        sweep_md, "",
        main_md, "",
        significance, "",
        verify_md, "",
    ]
    (out_dir / "RESULTS_BASELINES.md").write_text("\n".join(md), encoding="utf-8")

    def _ser(d):
        return {nm: {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}
                for nm, agg in d.items()}

    (out_dir / "results_baselines.json").write_text(json.dumps({
        "regime": regime, "config": vars(cfg), "n": n,
        "tune_seeds": list(TUNE_SEEDS), "test_seeds": list(TEST_SEEDS),
        "seed_stride": SEED_STRIDE, "sweep_budget": SWEEP_BUDGET,
        "selection_metric": SELECTION_METRIC, "pool_size": pool_size,
        "old_selected_from_n03": sel_old,
        "new_tune_scores": tune_scores_new, "new_selected": sel_new,
        "test_main": _ser(main), "order": order,
        "beats_random": wins_by_name,
    }, indent=2), encoding="utf-8")

    print(sweep_md)
    print("\n" + main_md.replace("### ", "== "))
    print("\n" + significance.replace("### ", "== "))
    print("\n" + verify_md.replace("### ", "== "))
    print(f"\nWrote {out_dir / 'RESULTS_BASELINES.md'} and {out_dir / 'results_baselines.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N07: additional retrieval baselines")
    p.add_argument("--regime", choices=("pure", "mixed"), default="pure")
    p.add_argument("--n", type=int, default=300, help="scenarios per seed")
    p.add_argument("--out", type=str, default="results_baselines")
    p.add_argument("--n-distractors", type=int, default=20,
                    help="default 20 = N01's realistic-pool value")
    p.add_argument("--n-noise", type=int, default=55,
                    help="default 55 = N01's realistic-pool value")
    return p.parse_args()


if __name__ == "__main__":
    _args = parse_args()
    asyncio.run(run_regime(_args.regime, _args))
