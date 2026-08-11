"""N16: scale stress test (also feeds N13's latency item, per NIGHT_QUEUE.md's own note).

Two questions:
  1. Where, if anywhere, does tcmf_add's causal@5 margin over graph_ppr close as the candidate
     pool grows past N01's realistic pool (~80) toward 1000+?
  2. What does bounded-backward-BFS + fusion cost, in wall-clock time, versus plain semantic
     ranking, as the pool grows? The causal graph itself is a fixed-length chain
     (chain_len events) regardless of pool size in this benchmark - memories, not graph nodes,
     are what scale - so this also directly measures whether BFS stays cheap while a full
     O(pool) ranking pass grows, which is the claim being tested.

Run:
    python -m tcmfbench.run_scale --out results_scale
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .generator import GenConfig, generate_many
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci

# Pool sizes: N01's small pool (17), N01's realistic pool (78), then past 1000. Distractors and
# noise scale together, holding their ratio fixed; chain_len (and so graph size) never changes.
POOL_POINTS = [
    {"n_distractors": 6, "n_noise": 8},      # pool 17 (N01 small, reproducibility check)
    {"n_distractors": 20, "n_noise": 55},    # pool 78 (N01 realistic, reproducibility check)
    {"n_distractors": 100, "n_noise": 275},  # pool ~378
    {"n_distractors": 260, "n_noise": 715},  # pool ~978
    {"n_distractors": 400, "n_noise": 1100}, # pool ~1503
]
RECALL_N = 30          # scenarios per pool point for the recall/margin sweep
LATENCY_N = 15         # scenarios per pool point for the latency sweep (timed individually)
SEED = 0


def _pool_size(pt: dict) -> int:
    return pt["n_distractors"] + pt["n_noise"] + 4  # +4 = chain_len-1 gold witnesses + crisis...
    # (approximate label only; the real pool_size is read off the materialized scenario below)


def _score(ranked, mat) -> dict[str, float]:
    return {
        "recall@5": MT.recall_at_k(ranked, mat.gold_ids, 5),
        "causal@5": MT.recall_at_k(ranked, mat.gold_causal, 5) if mat.gold_causal else
                    MT.recall_at_k(ranked, mat.gold_ids, 5),
        "root_rank": MT.rank_of(ranked, mat.root_id) or (len(ranked) + 1),
    }


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _recall_sweep(mats: list) -> dict:
    methods = {
        "tcmf_add": lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=0.45, clean=True),
        "graph_ppr": M.rank_graph_ppr,
    }
    raw = {name: [] for name in methods}
    for mat in mats:
        for name, fn in methods.items():
            raw[name].append(_score(await _order(fn, mat), mat))
    out = {}
    for name, rows in raw.items():
        out[name] = {}
        for k in rows[0]:
            import numpy as np
            vals = np.array([r[k] for r in rows], dtype=float)
            out[name][k] = bootstrap_ci(vals, seed=0)
    return out


def _timed(fn, mat, reps: int = 1) -> float:
    """Median wall-clock seconds for one call to a synchronous ranking function."""
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(mat)
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[len(times) // 2]


def _latency_sweep(mats: list) -> dict:
    """Median latency (seconds) per scenario for the BFS-alone step, plain semantic ranking,
    and full additive-fusion ranking, at this pool size."""
    bfs_times, semantic_times, fusion_times = [], [], []
    for mat in mats:
        bfs_times.append(_timed(
            lambda m: m.graph.predecessors(m.scenario.crisis_event_id, max_depth=4), mat))
        semantic_times.append(_timed(M.rank_semantic, mat))
        fusion_times.append(_timed(
            lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=0.45, clean=True), mat))
    bfs_times.sort(); semantic_times.sort(); fusion_times.sort()
    mid = len(mats) // 2
    return {
        "bfs_only_s": bfs_times[mid],
        "semantic_s": semantic_times[mid],
        "fusion_s": fusion_times[mid],
    }


def _check_reproduces_n01(pool_size: int, recall: dict) -> str | None:
    if pool_size == 17:
        return ("small-pool reproducibility check: causal@5 should be ~1.00 for both methods "
                "at this size, matching Table tab:main/tab:more-baselines")
    if pool_size == 78:
        return ("realistic-pool reproducibility check: should match N01/results_main_scale's "
                "causal_only=1.00 vs graph_ppr=0.67 pattern")
    return None


async def run(args) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for pt in POOL_POINTS:
        cfg = GenConfig(n_distractors=pt["n_distractors"], n_noise=pt["n_noise"])
        recall_scs = generate_many(RECALL_N, cfg, base_seed=SEED)
        recall_mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in recall_scs]
        pool_size = len(recall_mats[0].all_ids)
        print(f"pool={pool_size} (n_distractors={pt['n_distractors']}, "
              f"n_noise={pt['n_noise']}): recall sweep (n={RECALL_N})...")
        recall = await _recall_sweep(recall_mats)

        latency_scs = generate_many(LATENCY_N, cfg, base_seed=SEED + 500_000)
        latency_mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in latency_scs]
        print(f"pool={pool_size}: latency sweep (n={LATENCY_N})...")
        latency = _latency_sweep(latency_mats)

        note = _check_reproduces_n01(pool_size, recall)
        rows.append({
            "pool_size": pool_size, "n_distractors": pt["n_distractors"],
            "n_noise": pt["n_noise"], "recall": recall, "latency": latency, "note": note,
        })
        print(f"  causal@5: tcmf_add={recall['tcmf_add']['causal@5'][0]:.3f}  "
              f"graph_ppr={recall['graph_ppr']['causal@5'][0]:.3f}  "
              f"| latency(ms): bfs={latency['bfs_only_s']*1000:.3f}  "
              f"semantic={latency['semantic_s']*1000:.3f}  fusion={latency['fusion_s']*1000:.3f}")

    margin_closes_at = None
    for r in rows:
        margin = r["recall"]["tcmf_add"]["causal@5"][0] - r["recall"]["graph_ppr"]["causal@5"][0]
        r["causal5_margin"] = margin
        if margin_closes_at is None and margin <= 0.02:
            margin_closes_at = r["pool_size"]

    lines = [
        "# TCMF Benchmark: Scale Stress Test (N16, also feeds N13's latency item)",
        "",
        f"Pure regime, {RECALL_N} scenarios/point (recall), {LATENCY_N} scenarios/point "
        f"(latency, median of one timed call each), seed={SEED}. chain_len fixed at 4 "
        "throughout - graph size never changes, only the memory pool does.",
        "",
        "| pool | tcmf_add causal@5 | graph_ppr causal@5 | margin | BFS-only (ms) | "
        "semantic (ms) | fusion (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['pool_size']} | {r['recall']['tcmf_add']['causal@5'][0]:.3f} "
            f"[{r['recall']['tcmf_add']['causal@5'][1]:.3f},"
            f"{r['recall']['tcmf_add']['causal@5'][2]:.3f}] | "
            f"{r['recall']['graph_ppr']['causal@5'][0]:.3f} "
            f"[{r['recall']['graph_ppr']['causal@5'][1]:.3f},"
            f"{r['recall']['graph_ppr']['causal@5'][2]:.3f}] | "
            f"{r['causal5_margin']:+.3f} | {r['latency']['bfs_only_s']*1000:.3f} | "
            f"{r['latency']['semantic_s']*1000:.3f} | {r['latency']['fusion_s']*1000:.3f} |"
        )
    lines += [
        "",
        f"**Margin closes (causal@5 gap <= 0.02) at pool size:** "
        f"{margin_closes_at if margin_closes_at is not None else 'never, in the tested range'}",
        "",
    ]
    (out_dir / "RESULTS_SCALE.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "results_scale.json").write_text(json.dumps({
        "recall_n": RECALL_N, "latency_n": LATENCY_N, "seed": SEED,
        "rows": rows, "margin_closes_at_pool": margin_closes_at,
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {out_dir / 'RESULTS_SCALE.md'} and {out_dir / 'results_scale.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N16: scale stress test")
    p.add_argument("--out", type=str, default="results_scale")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
