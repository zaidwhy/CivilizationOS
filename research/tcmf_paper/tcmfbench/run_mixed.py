"""Mixed-regime experiment: show that additive TCMF beats BOTH the causal-only oracle and
semantic RAG, because neither signal alone recovers both kinds of gold.

    python -m tcmfbench.run_mixed --n 300 --out results_mixed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .mixed import MixedConfig, generate_many_mixed
from . import methods as M
from . import metrics as MT

KS = (3, 5, 10)

# N01: same disjoint-seed contract as run_eval.py (see test_n01_scale.py).
SEED_STRIDE = 100_000


def _score(ranked, mat) -> dict[str, float]:
    out = {f"recall@{k}": MT.recall_at_k(ranked, mat.gold_ids, k) for k in KS}
    out["causal@5"] = MT.recall_at_k(ranked, mat.gold_causal, 5)
    out["semantic@5"] = MT.recall_at_k(ranked, mat.gold_semantic, 5)
    out["root_mrr"] = MT.reciprocal_rank(ranked, mat.root_id)
    out["root_rank"] = MT.rank_of(ranked, mat.root_id) or (len(ranked) + 1)
    return out


def _agg(rows):
    return {k: (st.mean(r[k] for r in rows),
                st.pstdev([r[k] for r in rows]) if len(rows) > 1 else 0.0)
            for k in rows[0]}


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _eval_raw(mats, method_fns) -> dict[str, list[dict]]:
    per = {n: [] for n in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            per[name].append(_score(await _order(fn, mat), mat))
    return per


def _eval_agg(per: dict) -> dict:
    return {n: _agg(rows) for n, rows in per.items()}


async def _eval(mats, method_fns):
    return _eval_agg(await _eval_raw(mats, method_fns))


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


_COLS = [f"recall@{k}" for k in KS] + ["causal@5", "semantic@5", "root_mrr", "root_rank"]


def _table(title, results, order=None):
    names = order or list(results)
    lines = [f"### {title}", "", "| method | " + " | ".join(_COLS) + " |",
             "|" + "---|" * (len(_COLS) + 1)]
    for n in names:
        a = results[n]
        cells = [f"{a[c][0]:.2f}±{a[c][1]:.2f}" if c != "root_rank" else f"{a[c][0]:.1f}"
                 for c in _COLS]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _methods():
    return {
        "semantic_rag": M.rank_semantic,
        "episodic":     M.rank_episodic,
        "causal_only":  lambda m: M.rank_causal_only(m, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    M.rank_tcmf_multiplicative,                       # OLD operator (pre-fix)
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0),               # REAL retriever (fixed)
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, clean=True),
    }


ORDER = ["semantic_rag", "episodic", "causal_only", "graph_ppr",
         "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]


def _mats(cfg, n, seed):
    return [M.materialize(sc, cfg.max_mem_per_citizen)
            for sc in generate_many_mixed(n, cfg, base_seed=seed)]


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = args.n
    seeds = _parse_seeds(args)
    multiseed = bool(args.seeds)
    overrides = _cfg_overrides(args)

    base = MixedConfig(**overrides)

    per_seed_raw: dict[int, dict[str, list[dict]]] = {}
    mats_by_seed: dict[int, list] = {}
    for s in seeds:
        base_seed = s * SEED_STRIDE if multiseed else s
        ms = _mats(base, n, base_seed)
        mats_by_seed[s] = ms
        per_seed_raw[s] = await _eval_raw(ms, _methods())

    pooled_raw = {name: sum((per_seed_raw[s][name] for s in seeds), [])
                  for name in _methods()}
    main = _eval_agg(pooled_raw)
    mats = sum(mats_by_seed.values(), [])
    n_total = len(mats)
    pool_size = len(mats[0].all_ids) if mats else 0

    seed_stability = None
    if len(seeds) > 1:
        headline = ["semantic_rag", "causal_only", "tcmf_add", "tcmf_shipped"]
        seed_stability = {
            s: {m: _agg(per_seed_raw[s][m])["recall@10"][0] for m in headline}
            for s in seeds
        }

    # lambda tradeoff: causal weight vs which gold type is recovered
    lam_ab = await _eval(mats, {
        f"additive l={lam}": (lambda m, lam=lam: M.rank_tcmf_additive(m, lam=lam, clean=True))
        for lam in (0.5, 1, 2, 3, 4)
    })

    # edge-dropout robustness curve (overall recall@10)
    drop_methods = {
        "semantic_rag": M.rank_semantic,
        "causal_only":  lambda m: M.rank_causal_only(m, clean=True),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True),
    }
    dropouts = [0.0, 0.25, 0.5, 0.75, 1.0]
    curve = {}
    for p in dropouts:
        dm = sum((_mats(MixedConfig(edge_dropout=p, **overrides),
                         n, (s * SEED_STRIDE if multiseed else s)) for s in seeds), [])
        res = await _eval(dm, drop_methods)
        curve[p] = {m: res[m]["recall@10"][0] for m in drop_methods}

    ctbl = ["### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)",
            "", "| method | " + " | ".join(f"drop={p}" for p in dropouts) + " |",
            "|" + "---|" * (len(dropouts) + 1)]
    for m in drop_methods:
        ctbl.append(f"| {m} | " + " | ".join(f"{curve[p][m]:.2f}" for p in dropouts) + " |")

    seed_tbl_lines = []
    if seed_stability is not None:
        seed_tbl_lines = ["### Seed stability: recall@10 per individual seed (not pooled)", "",
                           "| seed | " + " | ".join(headline) + " |",
                           "|" + "---|" * (len(headline) + 1)]
        for s in seeds:
            row = seed_stability[s]
            seed_tbl_lines.append(f"| {s} | " + " | ".join(f"{row[m]:.2f}" for m in headline) + " |")

    md = [
        "# TCMF Benchmark: Mixed Regime",
        "",
        f"Scenarios: {n} per seed x {len(seeds)} seed(s) = {n_total} total | "
        f"seeds: {seeds} ({'multi-seed, stride ' + str(SEED_STRIDE) if multiseed else 'single-seed legacy mode'}) | "
        f"chain_len: {base.chain_len} | "
        f"semantic_gold: {base.n_semantic_gold} | distractors: {base.n_distractors} | "
        f"noise: {base.n_noise} | pool/scenario: {pool_size} | total gold: {base.total_gold()} "
        f"({base.chain_len - 1} causal + {base.n_semantic_gold} semantic)",
        "",
        "Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold "
        "(graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). "
        "Additive TCMF should dominate both single-signal baselines on overall recall. Means "
        "pooled across all seeds.",
        "",
        _table("Main comparison (mixed regime)", main, ORDER),
        "",
        *([("\n".join(seed_tbl_lines)), ""] if seed_tbl_lines else []),
        _table("Additive lambda tradeoff (causal@5 vs semantic@5)", lam_ab),
        "",
        "\n".join(ctbl),
        "",
    ]
    (out / "RESULTS_MIXED.md").write_text("\n".join(md), encoding="utf-8")
    (out / "results_mixed.json").write_text(json.dumps({
        "config": vars(base), "n": n, "seeds": seeds, "multiseed": multiseed,
        "seed_stride": SEED_STRIDE if multiseed else None,
        "n_total_scenarios": n_total, "pool_size": pool_size,
        "seed_stability_recall_at_10": seed_stability,
        "main": {nm: {k: {"mean": v[0], "std": v[1]} for k, v in a.items()}
                 for nm, a in main.items()},
        "lambda_tradeoff": {nm: {k: {"mean": v[0], "std": v[1]} for k, v in a.items()}
                            for nm, a in lam_ab.items()},
        "dropout_curve": {str(p): curve[p] for p in dropouts},
    }, indent=2), encoding="utf-8")

    print(_table("Main comparison (mixed regime)", main, ORDER).replace("### ", "== "))
    if seed_tbl_lines:
        print("\n" + "\n".join(seed_tbl_lines).replace("### ", "== "))
    print("\n" + "\n".join(ctbl).replace("### ", "== "))
    print(f"\nWrote {out/'RESULTS_MIXED.md'} and {out/'results_mixed.json'}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results_mixed")
    p.add_argument("--n-distractors", type=int, default=None,
                    help="override MixedConfig.n_distractors")
    p.add_argument("--n-noise", type=int, default=None,
                    help="override MixedConfig.n_noise")
    p.add_argument("--seeds", type=str, default=None,
                    help="comma-separated base seeds for a multi-seed harness (N01), e.g. "
                         "'0,1,2,3,4'. Overrides --seed when set.")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
