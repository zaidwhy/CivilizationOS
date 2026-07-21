"""Real-text tier runner: same experiment as the mixed regime, but scenarios are
natural-language and embedded with Ollama nomic-embed-text.

    python -m tcmfbench.run_realtext --n 120 --out results_realtext

Requires Ollama running with `nomic-embed-text`. Embeddings are cached to
results_realtext/emb_cache.json, so only the first run hits the encoder.

Real nomic embeddings are anisotropic (unrelated sentences already sit at cosine ~0.5), so the
causal-similarity threshold is raised to 0.6 to keep distractors from leaking a spurious boost
(see FINDINGS.md). Otherwise the method set matches the mixed regime.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .embed_client import EmbedClient
from .realtext import RealConfig, generate_many_realtext
from . import methods as M
from . import metrics as MT

KS = (3, 5, 10)
THR = 0.60  # raised for anisotropic real embeddings


def _score(ranked, mat):
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


async def _eval(mats, method_fns):
    per = {n: [] for n in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            per[name].append(_score(await _order(fn, mat), mat))
    return {n: _agg(rows) for n, rows in per.items()}


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
        "causal_only":  lambda m: M.rank_causal_only(m, threshold=THR, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=THR),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=THR, clean=True),
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0, threshold=THR),
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, threshold=THR, clean=True),
    }


ORDER = ["semantic_rag", "episodic", "causal_only", "graph_ppr",
         "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ec = EmbedClient(cache_path=out / "emb_cache.json")
    n, seed = args.n, args.seed

    def mats(cfg):
        scs = generate_many_realtext(n, cfg, ec, base_seed=seed)
        return [M.materialize(sc, cfg.max_mem_per_citizen) for sc in scs]

    base = RealConfig()
    print(f"Embedding {n} scenarios (cache: {len(ec)} vectors so far)...")
    ms = mats(base)
    print(f"Embedded. Cache now {len(ec)} vectors. Scoring...")
    main = await _eval(ms, _methods())

    drop_methods = {
        "semantic_rag": M.rank_semantic,
        "causal_only":  lambda m: M.rank_causal_only(m, threshold=THR, clean=True),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=THR, clean=True),
    }
    dropouts = [0.0, 0.5, 1.0]
    curve = {}
    for p in dropouts:
        res = await _eval(mats(RealConfig(edge_dropout=p)), drop_methods)
        curve[p] = {m: res[m]["recall@10"][0] for m in drop_methods}

    ctbl = ["### Edge-dropout robustness (real text, overall recall@10)", "",
            "| method | " + " | ".join(f"drop={p}" for p in dropouts) + " |",
            "|" + "---|" * (len(dropouts) + 1)]
    for m in drop_methods:
        ctbl.append(f"| {m} | " + " | ".join(f"{curve[p][m]:.2f}" for p in dropouts) + " |")

    md = [
        "# TCMF Benchmark: Real-Text Tier (Ollama nomic-embed-text)",
        "",
        f"Scenarios: {n} | seed: {seed} | encoder: nomic-embed-text (768d) | "
        f"causal threshold: {THR} | domains: {len(__import__('tcmfbench.realtext', fromlist=['DOMAINS']).DOMAINS)}",
        "",
        "Natural-language scenarios; ground truth by construction, geometry by the encoder. "
        "`causal@5`/`semantic@5` = recall over each gold subset.",
        "",
        _table("Main comparison (real text)", main, ORDER),
        "",
        "\n".join(ctbl),
        "",
    ]
    (out / "RESULTS_REALTEXT.md").write_text("\n".join(md), encoding="utf-8")
    (out / "results_realtext.json").write_text(json.dumps({
        "n": n, "seed": seed, "threshold": THR,
        "main": {nm: {k: {"mean": v[0], "std": v[1]} for k, v in a.items()}
                 for nm, a in main.items()},
        "dropout_curve": {str(p): curve[p] for p in dropouts},
    }, indent=2), encoding="utf-8")

    print(_table("Main comparison (real text)", main, ORDER).replace("### ", "== "))
    print("\n" + "\n".join(ctbl).replace("### ", "== "))
    print(f"\nWrote {out/'RESULTS_REALTEXT.md'}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=120)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results_realtext")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
