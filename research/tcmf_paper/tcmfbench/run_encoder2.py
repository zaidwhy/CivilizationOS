"""N13: second encoder + per-encoder threshold tuning.

Re-runs the real-text tier under TWO independent encoder families - Ollama's nomic-embed-text
(the paper's primary encoder) and a local sentence-transformers model (all-MiniLM-L6-v2, no
server, pip-only) - on the identical scenarios, seeds, and held-out tune/test protocol N03
already established, so the two are directly comparable to each other rather than to a
possibly-stale committed table. Answers: is the causal-ancestor effect an artifact of nomic's
own embedding geometry, and is nomic's anisotropy threshold (0.45 -> 0.60) a nomic fact or a
universal one?

    python -m tcmfbench.run_encoder2 --n 120 --out results_encoder2

Requires Ollama (nomic-embed-text) for the primary encoder; the second encoder needs only
`pip install sentence-transformers` (first run downloads the model, ~90MB, then cached).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from .embed_client import EmbedClient, SentenceEmbedClient
from .realtext import RealConfig, generate_many_realtext
from . import methods as M
from . import metrics as MT

KS = (3, 5, 10)
THR_GRID = [0.30, 0.45, 0.60, 0.75, 0.90]
SELECTION_METRIC = "recall@5"
SELECTION_METHOD = "tcmf_add"
TUNE_N = 40
TEST_N = 80

ORDER = ["semantic_rag", "episodic", "causal_only", "graph_ppr",
         "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]
_COLS = [f"recall@{k}" for k in KS] + ["causal@5", "semantic@5", "root_mrr", "root_rank"]


def _methods(thr: float):
    return {
        "semantic_rag": M.rank_semantic,
        "episodic":     M.rank_episodic,
        "causal_only":  lambda m: M.rank_causal_only(m, threshold=thr, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=thr),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=thr, clean=True),
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0, threshold=thr),
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, threshold=thr, clean=True),
    }


def _score(ranked, mat) -> dict[str, float]:
    out = {f"recall@{k}": MT.recall_at_k(ranked, mat.gold_ids, k) for k in KS}
    out["causal@5"] = MT.recall_at_k(ranked, mat.gold_causal, 5)
    out["semantic@5"] = MT.recall_at_k(ranked, mat.gold_semantic, 5)
    out["root_mrr"] = MT.reciprocal_rank(ranked, mat.root_id)
    out["root_rank"] = MT.rank_of(ranked, mat.root_id) or (len(ranked) + 1)
    return out


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _eval(mats, method_fns) -> dict:
    per = {n: [] for n in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            per[name].append(_score(await _order(fn, mat), mat))
    return {n: {k: (st.mean(r[k] for r in rows),
                    st.pstdev([r[k] for r in rows]) if len(rows) > 1 else 0.0)
                for k in rows[0]}
            for n, rows in per.items()}


async def _select_threshold(tune_mats) -> tuple[float, dict[float, float]]:
    scored = {}
    for thr in THR_GRID:
        fn = _methods(thr)[SELECTION_METHOD]
        rows = [_score(await _order(fn, mat), mat) for mat in tune_mats]
        scored[thr] = st.mean(r[SELECTION_METRIC] for r in rows)
    best = max(THR_GRID, key=lambda t: (scored[t], -t))
    return best, scored


def _anisotropy(ec, mats: list, n_pairs: int = 200, seed: int = 0) -> float:
    """Mean cosine between random UNRELATED memory embeddings in the pooled real-text corpus
    - the direct measurement behind the "unrelated sentences already sit at cosine ~X" claim,
    computed per-encoder instead of quoted from one encoder's own number."""
    rng = np.random.default_rng(seed)
    embs = [np.asarray(mat.mem[i]["embedding"], dtype=np.float64)
            for mat in mats for i in mat.all_ids]
    if len(embs) < 2:
        return 0.0
    idx_a = rng.integers(0, len(embs), size=n_pairs)
    idx_b = rng.integers(0, len(embs), size=n_pairs)
    sims = []
    for a, b in zip(idx_a, idx_b):
        if a == b:
            continue
        va, vb = embs[a], embs[b]
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        sims.append(float(np.dot(va, vb) / denom) if denom > 0 else 0.0)
    return float(np.mean(sims))


def _table(title, results, thr):
    lines = [f"### {title} (threshold={thr})", "", "| method | " + " | ".join(_COLS) + " |",
             "|" + "---|" * (len(_COLS) + 1)]
    for n in ORDER:
        a = results[n]
        cells = [f"{a[c][0]:.2f}±{a[c][1]:.2f}" if c != "root_rank" else f"{a[c][0]:.1f}"
                 for c in _COLS]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def _run_encoder(name: str, ec, n: int, seed: int, out_dir: Path) -> dict:
    base = RealConfig()

    def mats(cfg, count, base_seed):
        scs = generate_many_realtext(count, cfg, ec, base_seed=base_seed)
        return [M.materialize(sc, cfg.max_mem_per_citizen) for sc in scs]

    print(f"[{name}] embedding {n} scenarios (cache: {len(ec)} vectors so far)...")
    tune_mats = mats(base, TUNE_N, seed)
    test_mats = mats(base, TEST_N, seed + 500_000)
    ec.flush()
    print(f"[{name}] embedded. cache now {len(ec)} vectors. tuning threshold...")

    thr, sweep = await _select_threshold(tune_mats)
    print(f"[{name}] selected threshold={thr} (tune sweep: {sweep})")

    test_results = await _eval(test_mats, _methods(thr))
    aniso = _anisotropy(ec, tune_mats + test_mats)
    dim = len(test_mats[0].mem[test_mats[0].all_ids[0]]["embedding"]) if test_mats else 0

    md = _table(f"{name}: TEST split (n={TEST_N})", test_results, thr)
    (out_dir / f"RESULTS_{name.upper()}.md").write_text(
        f"# {name} encoder - real-text tier\n\nDimension: {dim}\nAnisotropy (mean cosine, "
        f"unrelated pairs): {aniso:.3f}\nSelected threshold: {thr} (tune sweep: {sweep})\n\n"
        f"{md}\n", encoding="utf-8")

    return {
        "name": name, "dim": dim, "anisotropy": aniso, "selected_threshold": thr,
        "tune_sweep": sweep, "test_n": TEST_N, "tune_n": TUNE_N,
        "test_results": {nm: {k: {"mean": v[0], "std": v[1]} for k, v in a.items()}
                         for nm, a in test_results.items()},
        "recall5_order": sorted(ORDER, key=lambda nm: test_results[nm]["recall@5"][0],
                                reverse=True),
    }


async def run(args) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    nomic = EmbedClient(cache_path=out_dir / "emb_cache_nomic.json")
    minilm = SentenceEmbedClient(cache_path=out_dir / "emb_cache_minilm.json")

    results = []
    for name, ec in (("nomic-embed-text", nomic), ("all-MiniLM-L6-v2", minilm)):
        results.append(await _run_encoder(name, ec, args.n, args.seed, out_dir))

    a, b = results
    same_order = a["recall5_order"] == b["recall5_order"]

    lines = [
        "# TCMF Benchmark: Second Encoder Comparison (N13)",
        "",
        f"n={args.n} (tune={TUNE_N}, test={TEST_N}), seed={args.seed}, identical real-text "
        "domains and scenario seeds for both encoders - the only thing that changes is which "
        "encoder produced the embeddings.",
        "",
        "| encoder | dim | anisotropy (unrelated cosine) | selected tau | recall@5 order "
        "(TEST, descending) |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['name']} | {r['dim']} | {r['anisotropy']:.3f} | "
                     f"{r['selected_threshold']} | {' > '.join(r['recall5_order'])} |")
    lines += [
        "",
        f"**Method ordering preserved across encoders:** {same_order}",
        "",
        f"### {a['name']}",
        "",
        _table(f"{a['name']}: TEST split", {k: {m: (v['mean'], v['std']) for m, v in vv.items()}
                                            for k, vv in a['test_results'].items()},
              a["selected_threshold"]),
        "",
        f"### {b['name']}",
        "",
        _table(f"{b['name']}: TEST split", {k: {m: (v['mean'], v['std']) for m, v in vv.items()}
                                            for k, vv in b['test_results'].items()},
              b["selected_threshold"]),
        "",
    ]
    (out_dir / "RESULTS_ENCODER2.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "results_encoder2.json").write_text(json.dumps({
        "n": args.n, "seed": args.seed, "tune_n": TUNE_N, "test_n": TEST_N,
        "thr_grid": THR_GRID, "encoders": results, "same_order": same_order,
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {out_dir / 'RESULTS_ENCODER2.md'} and {out_dir / 'results_encoder2.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N13: second encoder comparison")
    p.add_argument("--n", type=int, default=TUNE_N + TEST_N)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results_encoder2")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
