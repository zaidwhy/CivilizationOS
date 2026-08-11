"""Run the TCMF benchmark: main comparison + ablations, fully offline and deterministic.

    python -m tcmfbench.run_eval --n 300 --out results/

Findings this harness is built to measure:
  F1  the task is adversarial to similarity (semantic/episodic RAG near zero recall);
  F2  the causal signal alone is sufficient (causal_only high recall);
  F3  the SHIPPED multiplicative fusion suppresses that signal (tcmf_mult ~ episodic);
  F4  a normalized additive fusion of the SAME scores recovers it (tcmf_add);
  F5  the depth weighting favors proximate over root causes; inverting it fixes root rank.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .generator import GenConfig, generate_many
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci, holm_bonferroni, wilcoxon_signed_rank

KS = (1, 3, 5, 10)
_COLS = [f"recall@{k}" for k in KS] + ["root_mrr", "root_rank", "ndcg@10"]

# N01: distinct --seeds entries are offset by this stride before being used as generator
# base seeds, so e.g. --seeds 0,1,2,3,4 with --n 300 cannot regenerate overlapping scenarios
# (generate_many draws base_seed .. base_seed+n-1). See test_n01_scale.py.
SEED_STRIDE = 100_000


def _score(ranked, gold, root) -> dict[str, float]:
    out = {f"recall@{k}": MT.recall_at_k(ranked, gold, k) for k in KS}
    out["root_mrr"] = MT.reciprocal_rank(ranked, root)
    out["root_rank"] = MT.rank_of(ranked, root) or (len(ranked) + 1)
    out["ndcg@10"] = MT.ndcg_at_k(ranked, gold, root, 10)
    return out


def _agg(rows: list[dict[str, float]], seed: int = 0) -> dict[str, tuple[float, float, float]]:
    """{metric: (mean, ci_lo, ci_hi)} via seeded percentile bootstrap over scenarios (N02)."""
    out = {}
    for k in rows[0]:
        vals = np.array([r[k] for r in rows], dtype=float)
        vals = vals[~np.isnan(vals)]
        out[k] = bootstrap_ci(vals, seed=seed) if len(vals) else (float("nan"),) * 3
    return out


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _eval_methods_raw(mats, method_fns: dict) -> dict[str, list[dict]]:
    per: dict[str, list[dict]] = {name: [] for name in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            order = await _order(fn, mat)
            per[name].append(_score(order, mat.gold_ids, mat.root_id))
    return per


def _eval_methods_agg(per: dict[str, list[dict]]) -> dict:
    return {name: _agg(rows) for name, rows in per.items()}


async def _eval_methods(mats, method_fns: dict) -> dict:
    return _eval_methods_agg(await _eval_methods_raw(mats, method_fns))


def _materialize(cfg, n, seed):
    return [M.materialize(sc, cfg.max_mem_per_citizen)
            for sc in generate_many(n, cfg, base_seed=seed)]


def _parse_seeds(args) -> list[int]:
    if args.seeds:
        return [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    return [args.seed]


def _cfg_overrides(args) -> dict:
    kw = {}
    if args.n_distractors is not None:
        kw["n_distractors"] = args.n_distractors
    if args.n_noise is not None:
        kw["n_noise"] = args.n_noise
    return kw


# ------------------------------------------------------------------ method definitions

def main_methods() -> dict:
    return {
        "random":       lambda m: M.rank_random(m, seed=1234),
        "recency":      M.rank_recency,
        "semantic_rag": M.rank_semantic,
        "episodic":     M.rank_episodic,                                   # real pipeline, l=0
        "causal_only":  lambda m: M.rank_causal_only(m, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    M.rank_tcmf_multiplicative,                        # OLD operator (pre-fix)
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),   # operator study
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0),                # REAL retriever (fixed)
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, clean=True),
    }


MAIN_ORDER = ["random", "recency", "semantic_rag", "episodic", "causal_only",
              "graph_ppr", "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]


# ------------------------------------------------------------------------- reporting

def _table(title: str, results: dict, order: list[str] | None = None) -> str:
    names = order or list(results)
    lines = [f"### {title}", "",
             "| method | " + " | ".join(_COLS) + " |",
             "|" + "---|" * (len(_COLS) + 1)]
    for name in names:
        agg = results[name]
        cells = [
            (f"{agg[c][0]:.2f} [{agg[c][1]:.2f}, {agg[c][2]:.2f}]" if c != "root_rank"
             else f"{agg[c][0]:.1f} [{agg[c][1]:.1f}, {agg[c][2]:.1f}]")
            for c in _COLS
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _significance_table(pooled_raw: dict[str, list[dict]], order: list[str], ref: str,
                         metrics: tuple[str, ...] = ("recall@5", "root_rank")) -> str:
    """Paired Wilcoxon signed-rank test, `ref` vs every other method in `order`, on each of
    `metrics`, per-scenario-paired (same scenario index across methods). Holm-Bonferroni
    corrected across the whole family of contrasts (N02)."""
    others = [m for m in order if m != ref and m in pooled_raw]
    ref_vals = {metric: np.array([r[metric] for r in pooled_raw[ref]]) for metric in metrics}
    rows, raw_p = [], []
    for m in others:
        for metric in metrics:
            other_vals = np.array([r[metric] for r in pooled_raw[m]])
            p = wilcoxon_signed_rank(ref_vals[metric], other_vals)
            diff = float(ref_vals[metric].mean() - other_vals.mean())
            rows.append((m, metric, diff))
            raw_p.append(p)
    adj_p = holm_bonferroni(raw_p) if raw_p else []
    lines = [
        f"### Significance: {ref} vs every baseline (paired Wilcoxon signed-rank, "
        f"Holm-Bonferroni corrected across all {len(raw_p)} contrasts)",
        "",
        f"Positive diff = {ref} higher (better for recall, worse for root_rank - lower "
        "root_rank is better). p_holm <= 0.05 is significant after correction.",
        "",
        "| baseline | metric | mean diff | p (raw) | p (holm) |",
        "|---|---|---|---|---|",
    ]
    for (m, metric, diff), p_raw, p_h in zip(rows, raw_p, adj_p):
        lines.append(f"| {m} | {metric} | {diff:+.3f} | {p_raw:.4f} | {p_h:.4f} |")
    return "\n".join(lines)


def _verify_null_contrast_is_null(pooled_raw: dict[str, list[dict]], ref: str) -> None:
    """N02's own verification criterion, checked against real run data (not just unit
    tests): a method against itself must return p ~= 1.0 and a bootstrap CI of the paired
    difference containing zero."""
    vals = np.array([r["recall@5"] for r in pooled_raw[ref]], dtype=float)
    p_self = wilcoxon_signed_rank(vals, vals)
    assert abs(p_self - 1.0) < 1e-9, f"self-contrast p should be 1.0, got {p_self}"
    zero_diff = vals - vals
    _, lo, hi = bootstrap_ci(zero_diff, seed=0)
    assert lo <= 0.0 <= hi, f"self-contrast CI should contain 0, got [{lo}, {hi}]"


async def run(args) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    overrides = _cfg_overrides(args)
    base = GenConfig(**overrides)
    n = args.n
    seeds = _parse_seeds(args)
    multiseed = bool(args.seeds)

    # ---- main comparison: pool scenarios across every --seeds entry (N01 multi-seed harness).
    # Each seed is offset by SEED_STRIDE so scenarios are guaranteed disjoint (see
    # test_n01_scale.py::test_seed_stride_gives_disjoint_scenarios), not just re-permuted. ----
    per_seed_raw: dict[int, dict[str, list[dict]]] = {}
    mats_by_seed: dict[int, list] = {}
    for s in seeds:
        base_seed = s * SEED_STRIDE if multiseed else s
        ms = _materialize(base, n, base_seed)
        mats_by_seed[s] = ms
        per_seed_raw[s] = await _eval_methods_raw(ms, main_methods())

    pooled_raw = {name: sum((per_seed_raw[s][name] for s in seeds), [])
                  for name in main_methods()}
    main = _eval_methods_agg(pooled_raw)
    mats = sum(mats_by_seed.values(), [])  # pooled scenarios feed every ablation below
    n_total = len(mats)

    # N02: paired significance, tcmf_add vs every other method, Holm-corrected. Verified
    # against real run data (not just the unit tests in test_stats.py): a method-against-
    # itself contrast must return p ~= 1.0 and a CI containing zero.
    _verify_null_contrast_is_null(pooled_raw, ref="tcmf_add")
    significance = _significance_table(pooled_raw, MAIN_ORDER, ref="tcmf_add")

    # ---- seed-stability check: does the headline margin hold on every individual seed, or
    # only in the pooled average? (guards against a fluke of a single base seed) ----
    seed_stability = None
    if len(seeds) > 1:
        headline = ["random", "semantic_rag", "causal_only", "tcmf_add", "tcmf_shipped"]
        seed_stability = {
            s: {m: _agg(per_seed_raw[s][m])["recall@10"][0] for m in headline}
            for s in seeds
        }

    # ---- analytic random-baseline sanity check: E[recall@k] of a uniform random ranking is
    # k/pool_size in closed form (test_n01_scale.py), independent of gold count. If the
    # empirical `random` baseline diverges from this, some pipeline stage is silently
    # re-capping the candidate pool. ----
    pool_size = len(mats[0].all_ids) if mats else 0
    analytic_random = {k: MT.analytic_random_recall_at_k(pool_size, k) for k in KS}
    empirical_random = {k: main["random"][f"recall@{k}"][0] for k in KS}

    # ---- ablation: fusion operator (same episodic + same causal boosts) ----
    fusion = await _eval_methods(mats, {
        "mult (old, l=0.6)":     lambda m: M.rank_tcmf_multiplicative(m, lam=0.6),
        "mult (old, l=8)":       lambda m: M.rank_tcmf_multiplicative(m, lam=8.0),
        "additive (l=4)":        lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),
        "rrf":                   lambda m: M.rank_tcmf_rrf(m, clean=True),
        "shipped retriever":     lambda m: M.rank_tcmf(m, lam=2.0),
    })

    # ---- ablation: additive lambda ----
    lam_ab = await _eval_methods(mats, {
        f"additive l={lam}": (lambda m, lam=lam: M.rank_tcmf_additive(m, lam=lam, clean=True))
        for lam in (0.5, 1, 2, 4, 8)
    })

    # ---- ablation: multiplicative lambda (N10/Fig 4 - the flat-low-lambda curve to set
    # against additive's, on the same mats/pool as lam_ab so the two overlay validly). Grid
    # centered on the old shipped default 0.6, matching run_tuned.py's tcmf_mult_lambda sweep;
    # 0.6 and 8 duplicate the "fusion" ablation above as a cross-check the two agree. ----
    mult_lam_ab = await _eval_methods(mats, {
        f"mult l={lam}": (lambda m, lam=lam: M.rank_tcmf_multiplicative(m, lam=lam))
        for lam in (0.1, 0.3, 0.6, 1.2, 2.4, 8)
    })

    # ---- ablation: causal_sim_threshold ----
    thr_ab = await _eval_methods(mats, {
        f"threshold={t}": (lambda m, t=t: M.rank_tcmf_additive(m, lam=4.0, threshold=t, clean=True))
        for t in (0.30, 0.45, 0.60, 0.75)
    })

    # ---- ablation: depth-weighting direction ----
    depth_ab = await _eval_methods(mats, {
        "favor proximate (shipped)": lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True, favor_root=False),
        "favor root (fix)":          lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True, favor_root=True),
    })

    # ---- ablation: difficulty (embedding alignment alpha) ----
    diff_rows = {}
    for a in (0.75, 0.80, 0.85, 0.90, 0.95):
        cfg = GenConfig(alpha_mem=a, alpha_query=a, **overrides)
        dm = sum((_materialize(cfg, n, (s * SEED_STRIDE if multiseed else s)) for s in seeds), [])
        diff_rows[f"alpha={a}"] = await _eval_methods(dm, {
            "semantic_rag": M.rank_semantic,
            "causal_only":  lambda m: M.rank_causal_only(m, clean=True),
            "tcmf_mult":    M.rank_tcmf_multiplicative,
            "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),
        })

    # ---- difficulty table is method x alpha on recall@5 ----
    diff_methods = ["semantic_rag", "causal_only", "tcmf_mult", "tcmf_add"]
    diff_tbl = ["### Ablation: difficulty vs recall@5 (lower alpha = noisier embeddings)", "",
                "| method | " + " | ".join(diff_rows) + " |",
                "|" + "---|" * (len(diff_rows) + 1)]
    for meth in diff_methods:
        cells = [f"{diff_rows[a][meth]['recall@5'][0]:.2f}" for a in diff_rows]
        diff_tbl.append(f"| {meth} | " + " | ".join(cells) + " |")

    gold = (base.chain_len - 1) * base.witnesses_per_ancestor

    rand_tbl = ["### Analytic vs empirical random baseline (N01 sanity check)", "",
                "| k | analytic k/pool | empirical random recall@k |",
                "|---|---|---|"]
    for k in KS:
        rand_tbl.append(f"| {k} | {analytic_random[k]:.4f} | {empirical_random[k]:.4f} |")

    seed_tbl_lines = []
    if seed_stability is not None:
        seed_tbl_lines = ["### Seed stability: recall@10 per individual seed (not pooled)", "",
                           "| seed | " + " | ".join(headline) + " |",
                           "|" + "---|" * (len(headline) + 1)]
        for s in seeds:
            row = seed_stability[s]
            seed_tbl_lines.append(f"| {s} | " + " | ".join(f"{row[m]:.2f}" for m in headline) + " |")

    md = [
        "# TCMF Benchmark Results",
        "",
        f"Scenarios: {n} per seed x {len(seeds)} seed(s) = {n_total} total | "
        f"seeds: {seeds} ({'multi-seed, stride ' + str(SEED_STRIDE) if multiseed else 'single-seed legacy mode'}) | "
        f"dim: {base.dim} | chain_len: {base.chain_len} | "
        f"distractors: {base.n_distractors} | noise: {base.n_noise} | pool/scenario: {pool_size} | "
        f"alpha_mem: {base.alpha_mem} | gold/scenario: {gold}",
        "",
        "Mean [95% bootstrap CI] over scenarios (pooled across all seeds; 10000 resamples, "
        "seed 0 - N02). `root_rank` = mean rank of the root-cause memory (lower better). The "
        "mechanism under test is the real `api.memory.tcmf.TCMFRetriever`; baselines and "
        "fusion variants share identical episodic scores and causal boosts.",
        "",
        _table("Main comparison", main, MAIN_ORDER), "",
        significance, "",
        "\n".join(rand_tbl), "",
        *([("\n".join(seed_tbl_lines)), ""] if seed_tbl_lines else []),
        _table("Ablation: fusion operator (F3/F4)", fusion), "",
        _table("Ablation: additive causal weight lambda", lam_ab), "",
        _table("Ablation: multiplicative causal weight lambda", mult_lam_ab), "",
        _table("Ablation: causal_sim_threshold", thr_ab), "",
        _table("Ablation: depth-weighting direction (F5)", depth_ab), "",
        "\n".join(diff_tbl), "",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    def _ser(d):
        return {nm: {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}
                for nm, agg in d.items()}
    (out_dir / "results.json").write_text(json.dumps({
        "config": vars(base), "n": n, "seeds": seeds, "multiseed": multiseed,
        "seed_stride": SEED_STRIDE if multiseed else None,
        "n_total_scenarios": n_total, "pool_size": pool_size,
        "analytic_random_recall": analytic_random, "empirical_random_recall": empirical_random,
        "seed_stability_recall_at_10": seed_stability,
        "main": _ser(main), "fusion": _ser(fusion), "lambda": _ser(lam_ab),
        "mult_lambda": _ser(mult_lam_ab),
        "threshold": _ser(thr_ab), "depth": _ser(depth_ab),
        "difficulty": {a: _ser(v) for a, v in diff_rows.items()},
        "significance_tcmf_add_vs_all": significance,
    }, indent=2), encoding="utf-8")

    print(_table("Main comparison", main, MAIN_ORDER).replace("### ", "== "))
    print("\n" + significance.replace("### ", "== "))
    print("\n" + "\n".join(rand_tbl).replace("### ", "== "))
    if seed_tbl_lines:
        print("\n" + "\n".join(seed_tbl_lines).replace("### ", "== "))
    print("\n" + _table("Fusion operator", fusion).replace("### ", "== "))
    print("\n" + "\n".join(diff_tbl).replace("### ", "== "))
    print(f"\nWrote {out_dir/'RESULTS.md'} and {out_dir/'results.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="TCMF benchmark runner")
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results")
    p.add_argument("--n-distractors", type=int, default=None,
                    help="override GenConfig.n_distractors (default: GenConfig's own default)")
    p.add_argument("--n-noise", type=int, default=None,
                    help="override GenConfig.n_noise (default: GenConfig's own default)")
    p.add_argument("--seeds", type=str, default=None,
                    help="comma-separated base seeds for a multi-seed harness (N01), e.g. "
                         "'0,1,2,3,4'. Each seed is offset by SEED_STRIDE and its scenarios "
                         "pooled into the reported means. Overrides --seed when set.")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
