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
import statistics as st
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .generator import GenConfig, generate_many
from . import methods as M
from . import metrics as MT

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


def _agg(rows: list[dict[str, float]]) -> dict[str, tuple[float, float]]:
    return {
        k: (st.mean(r[k] for r in rows),
            st.pstdev([r[k] for r in rows]) if len(rows) > 1 else 0.0)
        for k in rows[0]
    }


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
        cells = [f"{agg[c][0]:.2f}±{agg[c][1]:.2f}" if c != "root_rank"
                 else f"{agg[c][0]:.1f}" for c in _COLS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


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
        "Mean±std over scenarios (pooled across all seeds). `root_rank` = mean rank of the "
        "root-cause memory (lower better). The mechanism under test is the real "
        "`api.memory.tcmf.TCMFRetriever`; baselines and fusion variants share identical "
        "episodic scores and causal boosts.",
        "",
        _table("Main comparison", main, MAIN_ORDER), "",
        "\n".join(rand_tbl), "",
        *([("\n".join(seed_tbl_lines)), ""] if seed_tbl_lines else []),
        _table("Ablation: fusion operator (F3/F4)", fusion), "",
        _table("Ablation: additive causal weight lambda", lam_ab), "",
        _table("Ablation: causal_sim_threshold", thr_ab), "",
        _table("Ablation: depth-weighting direction (F5)", depth_ab), "",
        "\n".join(diff_tbl), "",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")

    def _ser(d):
        return {nm: {k: {"mean": v[0], "std": v[1]} for k, v in agg.items()}
                for nm, agg in d.items()}
    (out_dir / "results.json").write_text(json.dumps({
        "config": vars(base), "n": n, "seeds": seeds, "multiseed": multiseed,
        "seed_stride": SEED_STRIDE if multiseed else None,
        "n_total_scenarios": n_total, "pool_size": pool_size,
        "analytic_random_recall": analytic_random, "empirical_random_recall": empirical_random,
        "seed_stability_recall_at_10": seed_stability,
        "main": _ser(main), "fusion": _ser(fusion), "lambda": _ser(lam_ab),
        "threshold": _ser(thr_ab), "depth": _ser(depth_ab),
        "difficulty": {a: _ser(v) for a, v in diff_rows.items()},
    }, indent=2), encoding="utf-8")

    print(_table("Main comparison", main, MAIN_ORDER).replace("### ", "== "))
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
