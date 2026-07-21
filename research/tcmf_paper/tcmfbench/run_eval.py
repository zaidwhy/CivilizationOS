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


async def _eval_methods(mats, method_fns: dict) -> dict:
    per: dict[str, list[dict]] = {name: [] for name in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            order = await _order(fn, mat)
            per[name].append(_score(order, mat.gold_ids, mat.root_id))
    return {name: _agg(rows) for name, rows in per.items()}


def _materialize(cfg, n, seed):
    return [M.materialize(sc, cfg.max_mem_per_citizen)
            for sc in generate_many(n, cfg, base_seed=seed)]


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
    base = GenConfig()
    n, seed = args.n, args.seed

    # ---- main comparison ----
    mats = _materialize(base, n, seed)
    main = await _eval_methods(mats, main_methods())

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
        cfg = GenConfig(alpha_mem=a, alpha_query=a)
        dm = _materialize(cfg, n, seed)
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
    md = [
        "# TCMF Benchmark Results",
        "",
        f"Scenarios: {n} | seed: {seed} | dim: {base.dim} | chain_len: {base.chain_len} | "
        f"distractors: {base.n_distractors} | noise: {base.n_noise} | "
        f"alpha_mem: {base.alpha_mem} | gold/scenario: {gold}",
        "",
        "Mean±std over scenarios. `root_rank` = mean rank of the root-cause memory (lower better). "
        "The mechanism under test is the real `api.memory.tcmf.TCMFRetriever`; baselines and "
        "fusion variants share identical episodic scores and causal boosts.",
        "",
        _table("Main comparison", main, MAIN_ORDER), "",
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
        "config": vars(base), "n": n, "seed": seed,
        "main": _ser(main), "fusion": _ser(fusion), "lambda": _ser(lam_ab),
        "threshold": _ser(thr_ab), "depth": _ser(depth_ab),
        "difficulty": {a: _ser(v) for a, v in diff_rows.items()},
    }, indent=2), encoding="utf-8")

    print(_table("Main comparison", main, MAIN_ORDER).replace("### ", "== "))
    print("\n" + _table("Fusion operator", fusion).replace("### ", "== "))
    print("\n" + "\n".join(diff_tbl).replace("### ", "== "))
    print(f"\nWrote {out_dir/'RESULTS.md'} and {out_dir/'results.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="TCMF benchmark runner")
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
