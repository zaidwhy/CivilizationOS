"""N29: do the two regimes survive cluttered causal graphs?

Every reviewer named the same weakness: the graphs are clean four-event chains, and the only
leakage is one false edge written on the crisis topic. This run puts each scenario inside a
cluttered event log (``clutter.py``): unrelated background events with their own links, and
several false edges per graph from that background into the true chain, on topics drawn without
favouring the crisis. Memories are identical across clutter levels (paired).

Arms, recall@5 over all gold (causal + semantic), both depth weightings:
  add_l4          additive at its derived weight (the deployed setting)
  add_best        additive, best weight on the grid (oracle, for headroom)
  mult_raw_l16    multiplicative at the weight tuned on held-out clean data (transferred)
  mult_raw_best   multiplicative, best weight on the grid (oracle, chosen on the test data)
  mult_raw_limit  multiplicative as lambda -> infinity (rank by e*b, ties by e)
  mult_norm_best / mult_norm_limit   the same on the normalized episodic score addition uses
  causal / semantic                  each signal alone

Mechanism: the N26b pair count. A leaked pair is (i, j) with i causal-gold, j non-gold and
b_j > 0; it is mult-only unreachable when b_j < b_i and e_i/e_j <= b_j/b_i.

    python -m tcmfbench.run_clutter_n29
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .clutter import ClutterConfig, add_clutter_realtext, generate_many_clutter_mixed
from .embed_client import EmbedClient
from .mixed import MixedConfig
from .realtext import RealConfig, generate_many_realtext
from .run_eval import SEED_STRIDE
from .stats import bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_clutter_n29"
GRID = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

SYNTH = {
    "clean":            ClutterConfig(n_background=0),
    "bg16_k0":          ClutterConfig(n_background=16, n_false_edges=0),
    "bg16_k1":          ClutterConfig(n_background=16, n_false_edges=1),
    "bg16_k2":          ClutterConfig(n_background=16, n_false_edges=2),
    "bg16_k4":          ClutterConfig(n_background=16, n_false_edges=4),
    "bg16_k8":          ClutterConfig(n_background=16, n_false_edges=8),
    "messy_bg32_k4_d.2": ClutterConfig(n_background=32, n_false_edges=4, edge_dropout=0.2),
}
TEXT = {
    "bg16_k0": ClutterConfig(n_background=16, n_false_edges=0),
    "bg16_k2": ClutterConfig(n_background=16, n_false_edges=2),
    "bg16_k4": ClutterConfig(n_background=16, n_false_edges=4),
    "bg16_k8": ClutterConfig(n_background=16, n_false_edges=8),
}


def _rank(ids, score, tie=None):
    order = np.lexsort((tie, score))[::-1] if tie is not None else np.argsort(-score, kind="stable")
    return [ids[k] for k in order]


def _depth_stats(mat):
    anc = M._ancestor_map(mat, clean=True)
    return max(anc.values(), default=0), len(anc)


def _one(mat, thr, fr):
    ids = list(mat.all_ids)
    e_d = M._episodic_scores(mat)
    b_d = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
    e = np.array([e_d[i] for i in ids])
    eh_d = M._minmax(e_d)
    eh = np.array([eh_d[i] for i in ids])
    b = np.array([b_d[i] for i in ids])
    q = np.array(mat.scenario.query_embedding)
    sim = np.array([M._cosine(mat.mem[i]["embedding"], list(q)) for i in ids])

    def r5(rk):
        return MT.recall_at_k(rk, mat.gold_ids, 5)

    def c5(rk):
        return MT.recall_at_k(rk, mat.gold_causal, 5)

    row = {}
    for lam in GRID:
        row[f"add_l{lam:g}"] = r5(_rank(ids, eh + lam * b))
        row[f"mult_raw_l{lam:g}"] = r5(_rank(ids, e * (1 + lam * b)))
        row[f"mult_norm_l{lam:g}"] = r5(_rank(ids, eh * (1 + lam * b)))
    row["mult_raw_limit"] = r5(_rank(ids, e * b, tie=e))
    row["mult_norm_limit"] = r5(_rank(ids, eh * b, tie=eh))
    row["causal"] = r5(_rank(ids, b))
    row["semantic"] = r5(_rank(ids, sim))
    row["causal@5_add_l4"] = c5(_rank(ids, eh + 4.0 * b))
    row["causal@5_mult_raw_l16"] = c5(_rank(ids, e * (1 + 16.0 * b)))

    # Leaked pairs (i causal-gold, j non-gold, b_j > 0), split by which operator can order them:
    #   mult_only  e_i < e_j, b_j < b_i, e_i b_i <= e_j b_j : no multiplicative weight works (Prop 1a),
    #                                                       additive works above 1/(b_i-b_j)
    #   add_cap    e_i > e_j, b_j > b_i, e_i b_i >  e_j b_j : every multiplicative weight works,
    #                                                       additive only below (e^_i-e^_j)/(b_j-b_i)
    #   dominated  e_j >= e_i and b_j >= b_i                : no operator, no weight
    #   other      both operators work at a suitable weight
    # plus how often each operator misorders leaked pairs at its deployed/transferred weight.
    mo = cap = dom = oth = add_bad = mult_bad = 0
    for gi in mat.gold_causal:
        a = ids.index(gi)
        for j in range(len(ids)):
            if ids[j] in mat.gold_ids or b[j] <= 0:
                continue
            ei, ej, bi, bj = e[a], e[j], b[a], b[j]
            if ej >= ei and bj >= bi:
                dom += 1
            elif ei < ej and bj < bi and ei * bi <= ej * bj:
                mo += 1
            elif ei > ej and bj > bi and ei * bi > ej * bj:
                cap += 1
            else:
                oth += 1
            add_bad += (eh[a] + 4.0 * bi) <= (eh[j] + 4.0 * bj)
            mult_bad += ei * (1 + 16.0 * bi) <= ej * (1 + 16.0 * bj)
    return row, (mo, cap, dom, oth, add_bad, mult_bad)


def _summarize(mats, thr, fr):
    rows, pairs = [], np.zeros(6)
    for mat in mats:
        r, p = _one(mat, thr, fr)
        rows.append(r)
        pairs += p
    mean = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
    best = lambda pre: max(GRID, key=lambda l: mean[f"{pre}_l{l:g}"])
    lr, ln, la = best("mult_raw"), best("mult_norm"), best("add")
    tot = pairs[:4].sum()
    # paired difference: additive at its derived weight minus the best multiplicative variant
    cands = {f"mult_raw_l{lr:g}": mean[f"mult_raw_l{lr:g}"], "mult_raw_limit": mean["mult_raw_limit"],
             f"mult_norm_l{ln:g}": mean[f"mult_norm_l{ln:g}"], "mult_norm_limit": mean["mult_norm_limit"]}
    best_mult_arm = max(cands, key=cands.get)
    diff = [r["add_l4"] - r[best_mult_arm] for r in rows]
    ds = [_depth_stats(m) for m in mats]
    return {
        "n": len(mats),
        "add_l4": mean["add_l4"], "add_best": {"lambda": la, "recall@5": mean[f"add_l{la:g}"]},
        "mult_raw_l16": mean["mult_raw_l16"],
        "mult_raw_best": {"lambda": lr, "recall@5": mean[f"mult_raw_l{lr:g}"]},
        "mult_raw_limit": mean["mult_raw_limit"],
        "mult_norm_best": {"lambda": ln, "recall@5": mean[f"mult_norm_l{ln:g}"]},
        "mult_norm_limit": mean["mult_norm_limit"],
        "causal": mean["causal"], "semantic": mean["semantic"],
        "causal@5_add_l4": mean["causal@5_add_l4"], "causal@5_mult_raw_l16": mean["causal@5_mult_raw_l16"],
        "best_mult_arm": best_mult_arm, "best_mult": cands[best_mult_arm],
        "add_l4_minus_best_mult_ci": list(bootstrap_ci(diff)),
        "wins_losses_ties_vs_best_mult": [int(sum(d > 0 for d in diff)), int(sum(d < 0 for d in diff)),
                                          int(sum(d == 0 for d in diff))],
        "leaked_pairs": int(tot),
        "frac_mult_only_unreachable": float(pairs[0] / tot) if tot else 0.0,
        "frac_add_capped": float(pairs[1] / tot) if tot else 0.0,
        "frac_dominated": float(pairs[2] / tot) if tot else 0.0,
        "frac_misordered_add_l4": float(pairs[4] / tot) if tot else 0.0,
        "frac_misordered_mult_l16": float(pairs[5] / tot) if tot else 0.0,
        "mean_deepest_ancestor": float(np.mean([d for d, _ in ds])),
        "mean_n_ancestors": float(np.mean([n for _, n in ds])),
        "grid_means": {k: v for k, v in mean.items()},
    }


def part_synth():
    res = {}
    for name, ccfg in SYNTH.items():
        mcfg = MixedConfig(n_distractors=20, n_noise=55)
        mats = [M.materialize(sc, mcfg.max_mem_per_citizen)
                for s in range(5)
                for sc in generate_many_clutter_mixed(300, mcfg, ccfg, base_seed=s * SEED_STRIDE)]
        for fr, tag in ((False, "prox"), (True, "root")):
            res[f"{name}_{tag}"] = _summarize(mats, 0.45, fr)
            v = res[f"{name}_{tag}"]
            print(f"S {name} {tag} add4={v['add_l4']:.3f} mult16={v['mult_raw_l16']:.3f} "
                  f"best_mult={v['best_mult']:.3f}({v['best_mult_arm']}) causal={v['causal']:.3f} "
                  f"mo={v['frac_mult_only_unreachable']:.2f} cap={v['frac_add_capped']:.2f} pairs={v['leaked_pairs']} D={v['mean_deepest_ancestor']:.2f}", flush=True)
    return res


def part_text():
    cache = OUT / "emb_cache.json"
    if not cache.exists():  # start from the committed real-text cache, never write to it
        shutil.copyfile(ROOT / "results_realtext" / "emb_cache.json", cache)
    ec = EmbedClient(cache_path=cache)
    rcfg = RealConfig(n_domains=6)
    base = generate_many_realtext(120, rcfg, ec, base_seed=0)
    res = {}
    for name, ccfg in TEXT.items():
        mats = [M.materialize(add_clutter_realtext(sc, ccfg, i, ec), rcfg.max_mem_per_citizen)
                for i, sc in enumerate(base)]
        for thr in (0.60, 0.50):
            for fr, tag in ((False, "prox"), (True, "root")):
                k = f"{name}_tau{thr}_{tag}"
                res[k] = _summarize(mats, thr, fr)
                v = res[k]
                print(f"T {k} add4={v['add_l4']:.3f} mult16={v['mult_raw_l16']:.3f} "
                      f"best_mult={v['best_mult']:.3f} causal={v['causal']:.3f} "
                      f"mo={v['frac_mult_only_unreachable']:.2f} cap={v['frac_add_capped']:.2f} pairs={v['leaked_pairs']}", flush=True)
    return res


def main():
    OUT.mkdir(exist_ok=True)
    res = {"grid": GRID}
    for key, fn in (("synthetic", part_synth), ("realtext", part_text)):
        res[key] = fn()
        (OUT / "results_clutter_n29.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    hdr = ("| setting | add (l=4) | mult raw (l=16, transferred) | best mult (oracle) | add - best mult [95% CI] "
           "| causal alone | semantic alone | leaked pairs | mult-only unreachable | add-capped | misordered add4 / mult16 | deepest ancestor |")
    lines = ["# N29: cluttered causal graphs (recall@5, all gold)", ""]
    for key, title in (("synthetic", "Mixed regime, pool 80, n=1500, tau=0.45"),
                       ("realtext", "Real text, six domains, n=120")):
        lines += [f"## {title}", "", hdr, "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in res[key].items():
            lo, hi = v["add_l4_minus_best_mult_ci"][1:]
            lines.append(f"| {k} | {v['add_l4']:.3f} | {v['mult_raw_l16']:.3f} | {v['best_mult']:.3f} "
                         f"({v['best_mult_arm']}) | {v['add_l4_minus_best_mult_ci'][0]:+.3f} [{lo:+.3f}, {hi:+.3f}] "
                         f"| {v['causal']:.3f} | {v['semantic']:.3f} | {v['leaked_pairs']} | {v['frac_mult_only_unreachable']:.2f} "
                         f"| {v['frac_add_capped']:.2f} | {v['frac_misordered_add_l4']:.2f} / {v['frac_misordered_mult_l16']:.2f} "
                         f"| {v['mean_deepest_ancestor']:.2f} |")
        lines.append("")
    (OUT / "RESULTS_CLUTTER_N29.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
