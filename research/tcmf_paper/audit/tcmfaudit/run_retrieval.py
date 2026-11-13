"""Tier A: retrieval experiments on synthetic worlds. Offline, seeded, resumable.

    python -m tcmfaudit.run_retrieval                 # every experiment, n=500
    python -m tcmfaudit.run_retrieval --only A1 A5 --n 100

One JSONL row per (cell, seed, method) is appended to ``results/retrieval/<exp>.jsonl.gz``; a
rerun skips (cell, seed) pairs already on disk, so an interrupted run resumes where it stopped.
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
from dataclasses import replace
from functools import partial
from typing import Callable, Iterator

import numpy as np

from . import AUDIT_ROOT, graphs
from . import retrievers as R
from .world import World, WorldConfig, generate

TOP_K = 5
RESULTS = AUDIT_ROOT / "results" / "retrieval"
DEFAULT = WorldConfig()

GraphBuilder = Callable[[World, np.random.Generator], graphs.ObservedGraph]

GRAPH_MODES: dict[str, GraphBuilder] = {
    "chain_only": lambda w, rng: graphs.chain_only(w),
    "oracle": lambda w, rng: graphs.oracle(w),
    "shuffled": lambda w, rng: graphs.shuffled(w, rng),
    "no_crisis_id": lambda w, rng: graphs.no_crisis_id(w),
    "deployed": lambda w, rng: graphs.deployed(w),
    "deployed_all": lambda w, rng: graphs.deployed(w, link_all=True),
}


def noisy(p_drop: float, n_false: int) -> GraphBuilder:
    return lambda w, rng: graphs.noisy(w, rng, p_drop, n_false)


BASE_METHODS: dict[str, Callable] = {
    "random": R.rank_random,
    "oracle": R.rank_oracle,
    "chronological": R.rank_chronological,
    "vector": R.rank_vector,
    "episodic": R.rank_episodic,
    "graph_query": R.rank_graph_query,
    "graph_union": R.rank_graph_union,
    "graph_ppr": R.rank_graph_ppr,
    "two_hop": R.rank_two_hop,
    "tcmf_deployed": R.rank_tcmf_deployed,
    "tcmf_no_weak": partial(R.rank_tcmf_variant, weak=False),
    "boosted_then_episodic": R.rank_boosted_then_episodic,
}

V = R.rank_tcmf_variant
ABLATIONS: dict[str, Callable] = {
    "tcmf_deployed": R.rank_tcmf_deployed,
    "full_reimpl": V,
    "no_weak_ancestors": partial(V, weak=False),
    "no_normalize": partial(V, normalize=False),
    "depth_uniform": partial(V, depth_mode="uniform"),
    "depth_proximal": partial(V, depth_mode="proximal"),
    "threshold_0": partial(V, threshold=0.0),
    "threshold_0.60": partial(V, threshold=0.60),
    "no_recency": partial(V, recency=False),
    "no_importance": partial(V, importance=False),
    "no_relevance": partial(V, relevance=False),
    "causal_term_only": partial(V, relevance=False, recency=False, importance=False),
    "aggregate_mean": partial(V, aggregate="mean"),
    "multiplicative_16": partial(V, operator="mult", lam=16.0, normalize=False),
    "lambda_0": partial(V, lam=0.0),
    "lambda_0.5": partial(V, lam=0.5),
    "lambda_1": partial(V, lam=1.0),
    "lambda_2": partial(V, lam=2.0),
    "lambda_8": partial(V, lam=8.0),
    "lambda_16": partial(V, lam=16.0),
    "no_weak+depth_uniform": partial(V, weak=False, depth_mode="uniform"),
    "vector": R.rank_vector,
    "graph_union": R.rank_graph_union,
}


def pick(*names: str) -> dict[str, Callable]:
    return {n: BASE_METHODS[n] for n in names}


CORE = pick("vector", "episodic", "graph_query", "graph_union", "graph_ppr",
            "tcmf_deployed", "tcmf_no_weak")

Cell = tuple[str, WorldConfig, GraphBuilder, dict[str, Callable]]


def experiments() -> dict[str, list[Cell]]:
    exps: dict[str, list[Cell]] = {}
    exps["A0_controls"] = [
        ("paper_condition", DEFAULT, GRAPH_MODES["chain_only"], BASE_METHODS),
        ("shuffled_graph", DEFAULT, GRAPH_MODES["shuffled"], BASE_METHODS),
        ("no_crisis_id", DEFAULT, GRAPH_MODES["no_crisis_id"], BASE_METHODS),
    ]
    exps["A1_oracle"] = [("oracle", DEFAULT, GRAPH_MODES["oracle"], BASE_METHODS)]
    exps["A2_depth"] = [
        (f"depth={d}|{mode}", replace(DEFAULT, depth=d), GRAPH_MODES[mode], CORE)
        for d in range(1, 7) for mode in ("chain_only", "oracle")
    ]
    exps["A3_deployed_graph"] = [
        (f"{mode}|root_age={age[0]}-{age[1]}|rho={rho}",
         replace(DEFAULT, root_age=age, rho=rho), GRAPH_MODES[mode], CORE)
        for mode in ("deployed", "deployed_all")
        for age in ((60, 150), (5, 40))
        for rho in (0.0, 0.5)
    ]
    exps["A4_rho"] = [
        (f"rho={rho}|rho_decoy={'same' if tied else 0}|{gname}",
         replace(DEFAULT, rho=rho, rho_decoy=rho if tied else 0.0), builder, CORE)
        for rho in (0.0, 0.2, 0.4, 0.6, 0.8)
        for tied in (False, True)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("noisy", noisy(0.3, 2)))
        if not (tied and rho == 0.0)
    ]
    exps["A5_graph_noise"] = [
        (f"p_drop={p}|n_false={f}", DEFAULT, noisy(p, f), CORE)
        for p in (0.0, 0.25, 0.5, 0.75, 1.0) for f in (0, 1, 2, 4)
    ]
    exps["A6_beta"] = [
        (f"beta={beta}|{gname}", replace(DEFAULT, beta=beta), builder,
         pick("vector", "episodic", "two_hop", "graph_union", "tcmf_deployed", "tcmf_no_weak"))
        for beta in (0.0, 0.2, 0.4, 0.6)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("noisy", noisy(0.5, 2)),
                               ("deployed", GRAPH_MODES["deployed"]))
    ]
    exps["A7_ablation"] = [
        ("chain_only|depth=3", DEFAULT, GRAPH_MODES["chain_only"], ABLATIONS),
        ("oracle|depth=3", DEFAULT, GRAPH_MODES["oracle"], ABLATIONS),
        ("oracle|depth=2", replace(DEFAULT, depth=2), GRAPH_MODES["oracle"], ABLATIONS),
        ("noisy|depth=3", DEFAULT, noisy(0.3, 2), ABLATIONS),
        ("oracle|depth=3|rho=0.4", replace(DEFAULT, rho=0.4, rho_decoy=0.4), GRAPH_MODES["oracle"], ABLATIONS),
    ]
    big = replace(DEFAULT, n_noise=135)
    exps["A9_pool150"] = [
        ("chain_only", big, GRAPH_MODES["chain_only"], BASE_METHODS),
        ("oracle", big, GRAPH_MODES["oracle"], BASE_METHODS),
        ("noisy", big, noisy(0.3, 2), BASE_METHODS),
    ]
    # Added after the first run; see "Deviations" in PREREG.md for why.
    posthoc = {**pick("vector", "episodic", "graph_union", "tcmf_deployed", "tcmf_no_weak"),
               "event_log": R.rank_event_log, "event_log_union": R.rank_event_log_union}
    exps["P1_posthoc_event_log"] = [
        (name, DEFAULT, builder, posthoc)
        for name, builder in (("chain_only", GRAPH_MODES["chain_only"]), ("oracle", GRAPH_MODES["oracle"]),
                              ("shuffled", GRAPH_MODES["shuffled"]), ("deployed", GRAPH_MODES["deployed"]),
                              ("noisy", noisy(0.3, 2)))
    ] + [("oracle|depth=2", replace(DEFAULT, depth=2), GRAPH_MODES["oracle"], posthoc)]
    exps["P2_posthoc_few_symptoms"] = [
        (f"rho={rho}|{gname}", replace(DEFAULT, n_symptoms=2, rho=rho, rho_decoy=rho), builder, posthoc)
        for rho in (0.0, 0.2, 0.4, 0.6, 0.8)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("noisy", noisy(0.3, 2)))
    ]
    exps["P3_posthoc_log_size"] = [
        (f"other_events={k}|{gname}", replace(DEFAULT, n_decoy_events=k), builder, posthoc)
        for k in (0, 3, 6, 12, 18)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("noisy", noisy(0.3, 2)),
                               ("shuffled", GRAPH_MODES["shuffled"]))
        if not (gname == "shuffled" and k < DEFAULT.depth)
    ]
    # Added in answer to the independent review (REVIEW_LOG.md, objections 6-8).
    exps["R1_review_age_matched"] = [
        (gname, replace(DEFAULT, root_age=(10, 150), decoy_age=(10, 150)), builder, ABLATIONS)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("noisy", noisy(0.3, 2)))
    ]
    exps["R2_review_deep_false_edges"] = [
        (f"p_drop={p}|n_false={f}", DEFAULT, (lambda p_, f_: lambda w, rng: graphs.noisy_deep(w, rng, p_, f_))(p, f), posthoc)
        for p in (0.0, 0.25) for f in (0, 1, 2, 4)
    ]
    exps["R3_review_long_log"] = [
        (f"other_events={k}|{gname}", replace(DEFAULT, n_decoy_events=k), builder, posthoc)
        for k in (30, 50)
        for gname, builder in (("oracle", GRAPH_MODES["oracle"]), ("deployed_all", GRAPH_MODES["deployed_all"]))
    ]
    return exps


def score(world: World, ranking: list[int]) -> dict[str, float]:
    top = ranking[:TOP_K]
    gold, root, symptoms = world.causal_gold, world.root_gold, world.symptom_gold
    return {
        "root_hit": float(any(i in root for i in top)),
        "causal_recall": sum(i in gold for i in top) / min(TOP_K, len(gold)),
        "symptom_recall": sum(i in symptoms for i in top) / min(TOP_K, len(symptoms)),
        "decoy_in_top": float(sum(world.mem_label[i] == "decoy" for i in top)),
        "root_rank": float(min(ranking.index(i) for i in root) + 1),
    }


def run_cell(exp: str, cell: Cell, seeds: Iterator[int]) -> Iterator[dict]:
    name, cfg, build, methods = cell
    for seed in seeds:
        world = generate(cfg, seed)
        og = build(world, np.random.default_rng([seed, 7919]))
        quality = graphs.edge_quality(world, og)
        for method, fn in methods.items():
            ranking = fn(world, og, seed=seed) if method == "random" else fn(world, og)
            if sorted(ranking) != list(range(world.n)):
                raise RuntimeError(f"{method} did not return a permutation ({exp}/{name}/{seed})")
            yield {"exp": exp, "cell": name, "seed": seed, "method": method,
                   "pool": world.n, **score(world, ranking), **quality}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--only", nargs="*", default=None, help="experiment id prefixes, e.g. A1 A5")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    for exp, cells in experiments().items():
        if args.only and not any(exp.startswith(p) for p in args.only):
            continue
        path = RESULTS / f"{exp}.jsonl.gz"
        done: set[tuple[str, int]] = set()
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh]
            per_pair: dict[tuple[str, int], int] = {}
            for row in rows:
                per_pair[(row["cell"], row["seed"])] = per_pair.get((row["cell"], row["seed"]), 0) + 1
            n_methods = {c[0]: len(c[3]) for c in cells}
            done = {pair for pair, count in per_pair.items() if count == n_methods.get(pair[0])}
            if len(done) != len(per_pair):
                keep = [r for r in rows if (r["cell"], r["seed"]) in done]
                with gzip.open(path, "wt", encoding="utf-8") as fh:
                    fh.writelines(json.dumps(r) + "\n" for r in keep)
        started = time.perf_counter()
        with gzip.open(path, "at", encoding="utf-8") as fh:
            for cell in cells:
                todo = (s for s in range(args.n) if (cell[0], s) not in done)
                for row in run_cell(exp, cell, todo):
                    fh.write(json.dumps(row) + "\n")
        print(f"{exp}: {len(cells)} cells x n={args.n} in {time.perf_counter() - started:.1f}s -> {path.name}")


if __name__ == "__main__":
    main()
