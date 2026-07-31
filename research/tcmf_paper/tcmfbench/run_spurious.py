"""N04: spurious-edge robustness (the mirror image of the F7 dropout curve).

F7 only stresses MISSING causal edges. The more dangerous failure is a WRONG edge: a false
ancestor gets fabricated and linked directly into the crisis, aligned to the SAME topic as the
distractors (see `mixed.py`'s `spurious_edge_rate`). This script measures two things,
independently of the existing `edge_dropout` knob:

  1. Recall damage: does tcmf_add's overall recall@10 margin survive as spurious edges get more
     common, and at which rate does it drop below semantic_rag (the paper's honest
     operating-envelope claim)?
  2. Precision damage (not asked for by F7 at all): how often does a spurious edge promote a
     causally-irrelevant distractor into the top-5 an agent would actually read?

    python -m tcmfbench.run_spurious --out results_spurious
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .mixed import MixedConfig, generate_many_mixed
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci
from . import run_mixed  # reuse the N01 seed-stride contract + N02 bootstrap aggregator

SEED_STRIDE = run_mixed.SEED_STRIDE
SEEDS = (0, 1, 2, 3, 4)  # same 5-seed protocol N01/N02/N03 established as the realistic pool

# "coarse resolution", per the queue spec; these are the exact rates the queue item names.
SPURIOUS_RATES = (0.0, 0.05, 0.1, 0.2, 0.4)
DROPOUT_RATES_2D = (0.0, 0.2, 0.4)   # coarser than F7's 5-point curve - this is the 2-D grid,
                                     # not a replacement for F7's own 1-D dropout curve

# Methods stressed by the false-ancestor edge: every one of these consumes the causal graph
# (semantic_rag does not, and is the reference floor a fooled causal method could fall below).
_METHODS = {
    "semantic_rag": M.rank_semantic,
    "causal_only":  lambda m: M.rank_causal_only(m, clean=True),
    "graph_ppr":    M.rank_graph_ppr,
    "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),
    "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0),
}
GRID_METHODS = ("semantic_rag", "causal_only", "tcmf_add")  # 2-D grid: keep it to the trio F7
                                                             # already reports, at coarser n


def _score(mat, ranked) -> dict[str, float]:
    dist = M.distractor_ids(mat)
    return {
        "recall@5":  MT.recall_at_k(ranked, mat.gold_ids, 5),
        "recall@10": MT.recall_at_k(ranked, mat.gold_ids, 10),
        "causal@5":  MT.recall_at_k(ranked, mat.gold_causal, 5),
        "distractor_top5": MT.any_in_top_k(ranked, dist, 5),
    }


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _eval_raw(mats, method_fns) -> dict[str, list[dict]]:
    per = {n: [] for n in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            per[name].append(_score(mat, await _order(fn, mat)))
    return per


def _pooled_mats(n, n_distractors, n_noise, edge_dropout, spurious_edge_rate):
    cfg = MixedConfig(n_distractors=n_distractors, n_noise=n_noise,
                       edge_dropout=edge_dropout, spurious_edge_rate=spurious_edge_rate)
    mats = []
    for s in SEEDS:
        base_seed = s * SEED_STRIDE
        mats.extend(M.materialize(sc, cfg.max_mem_per_citizen)
                    for sc in generate_many_mixed(n, cfg, base_seed=base_seed))
    return mats


def _agg_metric(rows, metric, seed=0):
    vals = np.array([r[metric] for r in rows], dtype=float)
    vals = vals[~np.isnan(vals)]
    if not len(vals):
        return (float("nan"),) * 3
    return bootstrap_ci(vals, seed=seed)


def _first_crossover(rates, a_vals, b_vals) -> float | None:
    """First rate at which a_vals drops (strictly) below b_vals, given both are monotone-ish
    sequences aligned to `rates`. Returns None if `a` never falls below `b`."""
    for r, a, b in zip(rates, a_vals, b_vals):
        if a < b:
            return r
    return None


async def run(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = args.n
    n_distractors, n_noise = args.n_distractors, args.n_noise

    # ---- Part 1: spurious-only curve at dropout=0, full n, all 5 methods + precision metric.
    # p=0 here must reproduce results_mixed_scale exactly (same seeds, same pool, same n) -
    # verified separately below by loading that committed file directly. ----
    curve_raw: dict[float, dict[str, list[dict]]] = {}
    for p in SPURIOUS_RATES:
        mats = _pooled_mats(n, n_distractors, n_noise, edge_dropout=0.0, spurious_edge_rate=p)
        curve_raw[p] = await _eval_raw(mats, _METHODS)

    curve_agg = {
        p: {m: {k: _agg_metric(rows, k) for k in ("recall@5", "recall@10", "causal@5",
                                                    "distractor_top5")}
            for m, rows in curve_raw[p].items()}
        for p in SPURIOUS_RATES
    }

    # ---- p=0 reproducibility check against the committed N01-scale results (same seeds,
    # same pool, same n unless the caller overrides --n) ----
    repro_note = "not checked (--n overridden from the 300 N01 default)"
    if n == 300 and n_distractors == 20 and n_noise == 55:
        ref_path = Path(args.n01_ref)
        if ref_path.exists():
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            mine = curve_agg[0.0]
            diffs = {
                m: abs(mine[m]["recall@10"][0] - ref["main"][m]["recall@10"]["mean"])
                for m in ("semantic_rag", "causal_only", "tcmf_add") if m in ref["main"]
            }
            assert all(d < 1e-9 for d in diffs.values()), (
                f"p=0 recall@10 does not reproduce {ref_path} bit-for-bit: {diffs}"
            )
            repro_note = f"VERIFIED bit-for-bit against {ref_path} (max diff {max(diffs.values()):.2e})"
        else:
            repro_note = f"reference file {ref_path} not found - skipped"

    # ---- headline: which rate makes tcmf_add drop below semantic_rag on recall@10 ----
    tcmf_add_r10 = [curve_agg[p]["tcmf_add"]["recall@10"][0] for p in SPURIOUS_RATES]
    semantic_r10 = [curve_agg[p]["semantic_rag"]["recall@10"][0] for p in SPURIOUS_RATES]
    crossover = _first_crossover(SPURIOUS_RATES, tcmf_add_r10, semantic_r10)

    # ---- Part 2: coarse 2-D grid (dropout x spurious), smaller n, 3 methods, recall@10 only ----
    grid_n = args.grid_n
    grid: dict[tuple[float, float], dict[str, float]] = {}
    for d in DROPOUT_RATES_2D:
        for p in SPURIOUS_RATES:
            mats = _pooled_mats(grid_n, n_distractors, n_noise, edge_dropout=d,
                                 spurious_edge_rate=p)
            raw = await _eval_raw(mats, {k: _METHODS[k] for k in GRID_METHODS})
            grid[(d, p)] = {m: _agg_metric(raw[m], "recall@10")[0] for m in GRID_METHODS}

    # ---- render ----
    def fmt(v):
        m, lo, hi = v
        return f"{m:.2f} [{lo:.2f}, {hi:.2f}]"

    lines = [
        "# TCMF Benchmark: Spurious-Edge Robustness (N04)",
        "",
        f"Mixed regime, pool = {n_distractors + n_noise + 4 + 2} (chain_len 4 -> 3 causal-gold + "
        f"1 crisis, {n_noise} noise, {n_distractors} distractors, 2 semantic-gold), 5 seeds "
        f"(stride {SEED_STRIDE}), n={n} scenarios/seed for the curve, n={grid_n} for the 2-D "
        "grid (coarser, per the queue's own 'coarse resolution' instruction). A spurious edge "
        "is a single fabricated false-ancestor event, injected with probability p per scenario, "
        "aligned to the crisis surface topic (the SAME topic distractors and semantic-gold "
        "share) and linked directly into the crisis - independent of `edge_dropout`.",
        "",
        f"**p=0 reproducibility check:** {repro_note}",
        "",
        "### Spurious-rate curve (dropout=0 fixed), recall@10",
        "",
        "| method | " + " | ".join(f"p={p}" for p in SPURIOUS_RATES) + " |",
        "|" + "---|" * (len(SPURIOUS_RATES) + 1),
    ]
    for m in _METHODS:
        lines.append(f"| {m} | " + " | ".join(
            fmt(curve_agg[p][m]["recall@10"]) for p in SPURIOUS_RATES) + " |")
    lines += [
        "",
        "### Precision-side damage: P(a distractor is promoted into the top-5)",
        "",
        "| method | " + " | ".join(f"p={p}" for p in SPURIOUS_RATES) + " |",
        "|" + "---|" * (len(SPURIOUS_RATES) + 1),
    ]
    for m in _METHODS:
        lines.append(f"| {m} | " + " | ".join(
            fmt(curve_agg[p][m]["distractor_top5"]) for p in SPURIOUS_RATES) + " |")
    lines += [
        "",
        f"**Crossover: rate p at which tcmf_add's recall@10 first drops below semantic_rag's:** "
        f"{crossover if crossover is not None else 'never, across p in ' + str(SPURIOUS_RATES)}",
        "",
        "### 2-D grid: recall@10, dropout x spurious rate (coarse resolution)",
        "",
    ]
    for m in GRID_METHODS:
        lines.append(f"**{m}**")
        lines.append("")
        lines.append("| dropout \\ spurious | " + " | ".join(f"p={p}" for p in SPURIOUS_RATES) + " |")
        lines.append("|" + "---|" * (len(SPURIOUS_RATES) + 1))
        for d in DROPOUT_RATES_2D:
            row = [f"{grid[(d, p)][m]:.2f}" for p in SPURIOUS_RATES]
            lines.append(f"| drop={d} | " + " | ".join(row) + " |")
        lines.append("")

    (out / "RESULTS_SPURIOUS.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "results_spurious.json").write_text(json.dumps({
        "n": n, "grid_n": grid_n, "seeds": list(SEEDS), "seed_stride": SEED_STRIDE,
        "n_distractors": n_distractors, "n_noise": n_noise,
        "spurious_rates": list(SPURIOUS_RATES), "dropout_rates_2d": list(DROPOUT_RATES_2D),
        "p0_repro_check": repro_note,
        "curve": {
            str(p): {m: {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}
                     for m, agg in curve_agg[p].items()}
            for p in SPURIOUS_RATES
        },
        "crossover_tcmf_add_below_semantic_rag": crossover,
        "grid_recall_at_10": {f"{d}|{p}": grid[(d, p)] for d in DROPOUT_RATES_2D
                               for p in SPURIOUS_RATES},
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {out/'RESULTS_SPURIOUS.md'} and {out/'results_spurious.json'}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--grid-n", type=int, default=100,
                    help="scenarios per seed for the coarser 2-D grid (default 100, vs --n's "
                         "300 for the main curve - the grid has 3x more cells)")
    p.add_argument("--n-distractors", type=int, default=20,
                    help="matches N01's realistic-pool default; do not silently regress to "
                         "the old small pool")
    p.add_argument("--n-noise", type=int, default=55)
    p.add_argument("--out", type=str, default="results_spurious")
    p.add_argument("--n01-ref", type=str, default="results_mixed_scale/results_mixed.json",
                    help="committed N01-scale result file the p=0 curve must reproduce "
                         "bit-for-bit on recall@10")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
