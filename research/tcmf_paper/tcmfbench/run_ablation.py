"""N12: leave-one-out ablation of the four shipped fixes.

The paper claims four defects mattered (Section "Defects Surfaced in a Deployed Retriever").
This proves each one's individual contribution instead of asserting it, using
``methods.rank_tcmf_ablation`` - the same episodic scores and causal boosts every other
variant in this module uses, with exactly the toggled mechanism reverted to its pre-fix
behavior. Same pool/protocol as ``run_eval.py`` (pure regime, n=300, seed=0, pool=17), for
direct comparability with Tables tab:main/tab:operator/tab:lambda's own numbers.

Run:
    python -m tcmfbench.run_ablation --n 300 --out results_ablation
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .generator import GenConfig
from .mixed import MixedConfig, generate_many_mixed
from . import methods as M
from . import run_eval as RE

# The full (shipped) method: every fix applied. lam/threshold match tab:main's tcmf_add exactly.
FULL_KW = dict(additive=True, clean=True, favor_root=True, prune_k=None, lam=4.0, threshold=0.45)
PRUNE_K = 8  # "per-agent episodic top-8 prune", the exact defect main.tex names

# ---- leave-one-out arms: full method, minus exactly one fix, plus the (1)x(3) interaction
# N06/F8 flags and an all-broken sanity cross-check (should land near the old tcmf_mult numbers).
ARMS: dict[str, dict] = {
    "full (all 4 fixes)":            dict(FULL_KW),
    "minus fix1 (operator)":         dict(FULL_KW, additive=False),
    "minus fix2 (ancestor leak)":    dict(FULL_KW, clean=False),
    "minus fix3 (depth weight)":     dict(FULL_KW, favor_root=False),
    "minus fix4 (pre-fusion prune)": dict(FULL_KW, prune_k=PRUNE_K),
    "minus fix1+fix3 (interaction)": dict(FULL_KW, additive=False, favor_root=False),
    "all 4 reverted (sanity)":       dict(FULL_KW, additive=False, clean=False,
                                          favor_root=False, prune_k=PRUNE_K),
}

TAU_GRID = (0.30, 0.45, 0.60, 0.75)
DEPTH_CAP_GRID = (1, 2, 3, 4, 6, 8)
MEM_CAP_GRID = (8, 10, 12, 16, 20, 32)  # fix4 dose-response: excess over PRUNE_K=8


async def _eval_arms(mats: list, arms: dict[str, dict]) -> dict:
    fns = {name: (lambda m, kw=kw: M.rank_tcmf_ablation(m, **kw)) for name, kw in arms.items()}
    return await RE._eval_methods(mats, fns)


def _interaction_row(agg: dict, metric: str) -> tuple[float, float, float, float, float]:
    full = agg["full (all 4 fixes)"][metric][0]
    d1 = full - agg["minus fix1 (operator)"][metric][0]
    d3 = full - agg["minus fix3 (depth weight)"][metric][0]
    d13 = full - agg["minus fix1+fix3 (interaction)"][metric][0]
    return d1, d3, d1 + d3, d13, d13 - (d1 + d3)


def _interaction_table(agg: dict) -> str:
    """Quantify whether fix1 and fix3's combined effect is roughly additive or interacts.
    Additive would mean drop(1)+drop(3) ~= drop(1+3); a large residual means they interact.
    Reported on both recall@5 (the paper's headline metric) and root_mrr (the metric fix3
    actually moves on its own - F5's own framing is that with recall already at ceiling, the
    depth weight decides WHICH ancestor surfaces first, not whether it surfaces, so fix3's
    isolated recall@5 drop is expected to be near zero; root_mrr is where its individual
    contribution should show up)."""
    lines = [
        "### Interaction: fix1 (operator) x fix3 (depth weight)",
        "",
        "| metric | drop: fix1 alone | drop: fix3 alone | sum (additive prediction) | "
        "drop: both reverted | residual (interaction term) |",
        "|---|---|---|---|---|---|",
    ]
    for metric in ("recall@5", "root_mrr"):
        d1, d3, dsum, d13, residual = _interaction_row(agg, metric)
        lines.append(f"| {metric} | {d1:.4f} | {d3:.4f} | {dsum:.4f} | {d13:.4f} | "
                     f"{residual:+.4f} |")
    return "\n".join(lines)


async def run(args) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = GenConfig()
    mats = RE._materialize(cfg, args.n, args.seed)
    pool_size = len(mats[0].all_ids) if mats else 0

    main = await _eval_arms(mats, ARMS)
    interaction_md = _interaction_table(main)

    tau_arms = {f"tau={t}": dict(FULL_KW, threshold=t) for t in TAU_GRID}
    tau_agg = await _eval_arms(mats, tau_arms)

    depth_arms = {f"bfs_depth_cap={d}": dict(FULL_KW, bfs_depth_cap=d) for d in DEPTH_CAP_GRID}
    depth_agg = await _eval_arms(mats, depth_arms)

    # ---- Supplementary A: fix2 (ancestor leak) in the mixed regime, its natural habitat -
    # the leak specifically boosts distractors sharing the crisis's surface topic, and the
    # mixed regime is the one with an explicit semantic-gold distractor set near that topic.
    mixed_cfg = MixedConfig()
    mixed_mats = [M.materialize(sc, mixed_cfg.max_mem_per_citizen)
                  for sc in generate_many_mixed(args.n, mixed_cfg, base_seed=args.seed)]
    mixed_pool = len(mixed_mats[0].all_ids) if mixed_mats else 0
    fns_mixed = {name: (lambda m, kw=kw: M.rank_tcmf_ablation(m, **kw)) for name, kw in ARMS.items()}
    mixed_main = await RE._eval_methods(mixed_mats, fns_mixed)
    mixed_md = RE._table("N12 leave-one-out ablation, MIXED regime (n=%d, pool=%d)"
                         % (args.n, mixed_pool), mixed_main, list(ARMS))

    # ---- Supplementary B: fix4 (pre-fusion prune) dose-response - the benchmark's own
    # materialize() keeps every citizen AT OR BELOW max_mem_per_citizen by construction
    # (n_citizens = ceil(pool/max_mem_per_citizen)), so the default pool never actually
    # exercises an old top-8 cut. Sweeping max_mem_per_citizen past PRUNE_K reproduces
    # conditions where the old cap would actually have discarded memories before fusion, as it
    # did in a real, long-running simulation's organically-growing memory streams - and shows
    # this is a smooth function of the excess, not a single cherry-picked point.
    concentrated_cfg = GenConfig(n_distractors=20, n_noise=55)
    conc_arms = {"full (all 4 fixes)": FULL_KW, "minus fix4 (pre-fusion prune)":
                dict(FULL_KW, prune_k=PRUNE_K)}
    conc_fns = {name: (lambda m, kw=kw: M.rank_tcmf_ablation(m, **kw)) for name, kw in conc_arms.items()}
    conc_rows = []
    for mem_cap in MEM_CAP_GRID:
        concentrated_scs = RE.generate_many(args.n, concentrated_cfg, base_seed=args.seed)
        concentrated_mats = [M.materialize(sc, max_mem_per_citizen=mem_cap)
                             for sc in concentrated_scs]
        per_cit = max(sum(1 for i in concentrated_mats[0].all_ids
                          if concentrated_mats[0].mem[i]["citizen_id"] == c)
                     for c in {concentrated_mats[0].mem[i]["citizen_id"]
                               for i in concentrated_mats[0].all_ids})
        agg = await RE._eval_methods(concentrated_mats, conc_fns)
        conc_rows.append({"max_mem_per_citizen": mem_cap, "actual_per_citizen": per_cit,
                          "full_recall5": agg["full (all 4 fixes)"]["recall@5"],
                          "minus_fix4_recall5": agg["minus fix4 (pre-fusion prune)"]["recall@5"]})

    conc_md = ["### N12 fix4 dose-response: recall@5 vs. per-citizen memory count "
              f"(realistic pool, prune_k={PRUNE_K})", "",
              "| max_mem_per_citizen | actual per-citizen count | full recall@5 | "
              "minus-fix4 recall@5 |", "|---|---|---|---|"]
    for r in conc_rows:
        m = r["minus_fix4_recall5"]
        conc_md.append(f"| {r['max_mem_per_citizen']} | {r['actual_per_citizen']} | "
                       f"{r['full_recall5'][0]:.3f} | {m[0]:.3f} [{m[1]:.3f},{m[2]:.3f}] |")
    conc_md = "\n".join(conc_md)

    order = list(ARMS)
    main_md = RE._table("N12 leave-one-out ablation (pure regime, n=%d, pool=%d)"
                        % (args.n, pool_size), main, order)
    tau_md = RE._table("Tau sensitivity (full method, fix1-4 all applied)", tau_agg, list(tau_arms))
    depth_md = RE._table("BFS depth-cap sensitivity (full method, fix1-4 all applied)",
                         depth_agg, list(depth_arms))

    md = [
        "# TCMF Benchmark: leave-one-out ablation of the four shipped fixes (N12)",
        "",
        f"Pure regime, pool={pool_size}, n={args.n}, seed={args.seed} - identical scenarios to "
        "results_main/ (same GenConfig, same seed), so these numbers are directly comparable to "
        "Tables tab:main/tab:operator/tab:lambda. Mean [95% bootstrap CI] over scenarios "
        "(10000 resamples, seed 0 - N02).",
        "",
        main_md, "",
        interaction_md, "",
        tau_md, "",
        depth_md, "",
        mixed_md, "",
        conc_md, "",
    ]
    (out_dir / "RESULTS_ABLATION.md").write_text("\n".join(md), encoding="utf-8")

    def _ser(d):
        return {nm: {k: {"mean": v[0], "ci_lo": v[1], "ci_hi": v[2]} for k, v in agg.items()}
                for nm, agg in d.items()}

    (out_dir / "results_ablation.json").write_text(json.dumps({
        "config": vars(cfg), "n": args.n, "seed": args.seed, "pool_size": pool_size,
        "full_kw": FULL_KW, "prune_k": PRUNE_K,
        "arms": _ser(main), "tau_sweep": _ser(tau_agg), "depth_cap_sweep": _ser(depth_agg),
        "mixed_regime_pool_size": mixed_pool, "mixed_regime_arms": _ser(mixed_main),
        "fix4_dose_response": [
            {"max_mem_per_citizen": r["max_mem_per_citizen"],
             "actual_per_citizen": r["actual_per_citizen"],
             "full_recall5": {"mean": r["full_recall5"][0], "ci_lo": r["full_recall5"][1],
                              "ci_hi": r["full_recall5"][2]},
             "minus_fix4_recall5": {"mean": r["minus_fix4_recall5"][0],
                                    "ci_lo": r["minus_fix4_recall5"][1],
                                    "ci_hi": r["minus_fix4_recall5"][2]}}
            for r in conc_rows
        ],
        "interaction": {
            metric: {
                "full": main["full (all 4 fixes)"][metric][0],
                "minus_fix1": main["minus fix1 (operator)"][metric][0],
                "minus_fix3": main["minus fix3 (depth weight)"][metric][0],
                "minus_fix1_and_fix3": main["minus fix1+fix3 (interaction)"][metric][0],
            }
            for metric in ("recall@5", "root_mrr")
        },
    }, indent=2), encoding="utf-8")

    print(main_md)
    print("\n" + interaction_md)
    print("\n" + tau_md)
    print("\n" + depth_md)
    print("\n" + mixed_md)
    print("\n" + conc_md)
    print(f"\nWrote {out_dir / 'RESULTS_ABLATION.md'} and {out_dir / 'results_ablation.json'}")


def parse_args():
    p = argparse.ArgumentParser(description="N12: leave-one-out ablation")
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results_ablation")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
