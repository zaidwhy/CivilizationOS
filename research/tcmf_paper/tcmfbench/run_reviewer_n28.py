"""N28: the three experiments a reviewer asked for after the two-regime rewrite.

A. Operator isolation under leakage. N26 compared normalized ADDITIVE fusion against RAW
   multiplicative fusion, so the leakage gap mixed operator and score scale. Here, under the same
   leakage conditions, three variants share one normalization choice at a time:
     add_norm   = minmax(e) + lam*b            (the additive operator)
     mult_norm  = minmax(e) * (1 + lam*b)       (same normalized score, multiplicative operator)
     mult_raw   = e * (1 + lam*b)               (the deployed form)
   each over a dense lambda grid (0.25 .. 512) plus the lambda -> infinity limit, reporting the
   BEST recall@5 over the grid for the multiplicative variants (an oracle choice on the test
   data, which favours them) against additive at its derived lambda=4.
B. The pool-scaling comparison with graph_ppr at its held-out-tuned alpha (0.95), not 0.85.
C. The eight-domain check with multiplicative fusion at its held-out-tuned lambda=16, not 0.6.

Offline (real-text embeddings from committed caches).

    python -m tcmfbench.run_reviewer_n28
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .embed_client import EmbedClient
from .generator import GenConfig, generate_many
from .mixed import MixedConfig, generate_many_mixed
from .realtext import DOMAINS, RealConfig, generate_many_realtext
from .run_eval import SEED_STRIDE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_reviewer_n28"
GRID = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]


def _prep(mat, thr, fr):
    ids = list(mat.all_ids)
    e = M._episodic_scores(mat)
    b = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
    eh = M._minmax(e)
    return ids, np.array([e[i] for i in ids]), np.array([eh[i] for i in ids]), np.array([b[i] for i in ids])


def _r5(ids, score, mat, tie=None):
    order = np.lexsort((tie, score))[::-1] if tie is not None else np.argsort(-score, kind="stable")
    ranked = [ids[k] for k in order]
    return MT.recall_at_k(ranked, mat.gold_ids, 5)


def _arms_for(prepped):
    out = {"add_norm_l4": []}
    for lam in GRID:
        out[f"mult_raw_l{lam:g}"] = []
        out[f"mult_norm_l{lam:g}"] = []
    out["mult_raw_limit"] = []
    out["mult_norm_limit"] = []
    for mat, ids, e, eh, b in prepped:
        out["add_norm_l4"].append(_r5(ids, eh + 4.0 * b, mat))
        for lam in GRID:
            out[f"mult_raw_l{lam:g}"].append(_r5(ids, e * (1 + lam * b), mat))
            out[f"mult_norm_l{lam:g}"].append(_r5(ids, eh * (1 + lam * b), mat))
        out["mult_raw_limit"].append(_r5(ids, e * b, mat, tie=e))
        out["mult_norm_limit"].append(_r5(ids, eh * b, mat, tie=eh))
    m = {k: float(np.mean(v)) for k, v in out.items()}
    best_raw = max(GRID, key=lambda l: m[f"mult_raw_l{l:g}"])
    best_norm = max(GRID, key=lambda l: m[f"mult_norm_l{l:g}"])
    return {"means": m,
            "best_mult_raw": {"lambda": best_raw, "recall@5": m[f"mult_raw_l{best_raw:g}"]},
            "best_mult_norm": {"lambda": best_norm, "recall@5": m[f"mult_norm_l{best_norm:g}"]},
            "add_norm_l4": m["add_norm_l4"],
            "mult_raw_limit": m["mult_raw_limit"], "mult_norm_limit": m["mult_norm_limit"]}


def part_a():
    res = {}
    for p in (0.0, 0.1, 0.25, 0.5, 1.0):
        cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=p)
        mats = [M.materialize(sc, cfg.max_mem_per_citizen)
                for s in range(5) for sc in generate_many_mixed(300, cfg, base_seed=s * SEED_STRIDE)]
        for fr, tag in ((False, "prox"), (True, "root")):
            prepped = [(mat, *_prep(mat, 0.45, fr)) for mat in mats]
            res[f"spurious_p{p}_{tag}"] = _arms_for(prepped)
        print("A spurious", p, flush=True)
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    rt = [M.materialize(sc, RealConfig().max_mem_per_citizen)
          for sc in generate_many_realtext(120, RealConfig(n_domains=6), ec, base_seed=0)]
    for tau in (0.45, 0.5, 0.6):
        for fr, tag in ((False, "prox"), (True, "root")):
            prepped = [(mat, *_prep(mat, tau, fr)) for mat in rt]
            res[f"realtext_tau{tau}_{tag}"] = _arms_for(prepped)
        print("A realtext", tau, flush=True)
    return res


def part_b():
    pools = [(6, 8), (20, 55), (100, 275), (260, 715), (400, 1100)]
    res = {}
    for nd, nn in pools:
        cfg = GenConfig(n_distractors=nd, n_noise=nn)
        mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in generate_many(30, cfg, base_seed=0)]
        row = {}
        for name, fn in (("graph_ppr_a0.85", lambda m: M.rank_graph_ppr(m, alpha=0.85)),
                         ("graph_ppr_a0.95", lambda m: M.rank_graph_ppr(m, alpha=0.95)),
                         ("tcmf_add", lambda m: M.rank_tcmf_additive(m, lam=4.0, clean=True))):
            row[name] = float(np.mean([MT.recall_at_k(fn(m), m.gold_causal or m.gold_ids, 5) for m in mats]))
        res[str(nd + nn + 4)] = row
        print("B pool", nd + nn + 4, row, flush=True)
    return res


def part_c():
    n06 = json.load(open(ROOT / "results_n06" / "results_n06.json"))["domains"]
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    cfg = RealConfig()
    res = {}
    for di, dom in enumerate(DOMAINS):
        name = dom["name"]
        thr = n06[name]["threshold"]
        scs = generate_many_realtext(15, cfg, ec, base_seed=di * 10_000 + 10, domain_idx=di)
        mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in scs]
        row = {"threshold": thr}
        for arm, fn in (("add_l4", lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=thr, clean=True)),
                        ("mult_l0.6", lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=thr)),
                        ("mult_l16", lambda m: M.rank_tcmf_multiplicative(m, lam=16.0, threshold=thr))):
            row[arm] = float(np.mean([MT.recall_at_k(fn(m), m.gold_causal, 5) for m in mats]))
        res[name] = row
        print("C", name, row, flush=True)
    return res


def main():
    OUT.mkdir(exist_ok=True)
    res = {"grid": GRID}
    for key, fn in (("A_leakage_isolation", part_a), ("B_scale_tuned_ppr", part_b),
                    ("C_domains_tuned_mult", part_c)):
        res[key] = fn()  # saved after each part so a late crash cannot lose earlier work
        (OUT / "results_reviewer_n28.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = ["# N28: reviewer-requested checks", "",
             "## A. Operator isolation under leakage (recall@5; multiplicative = best over a dense lambda grid 0.25-512, oracle-chosen on test)", "",
             "| setting | add (norm, lam=4) | best mult (norm) [lam] | mult norm limit | best mult (raw) [lam] | mult raw limit |",
             "|---|---|---|---|---|---|"]
    for k, v in res["A_leakage_isolation"].items():
        lines.append(f"| {k} | {v['add_norm_l4']:.3f} | {v['best_mult_norm']['recall@5']:.3f} [{v['best_mult_norm']['lambda']:g}] | "
                     f"{v['mult_norm_limit']:.3f} | {v['best_mult_raw']['recall@5']:.3f} [{v['best_mult_raw']['lambda']:g}] | {v['mult_raw_limit']:.3f} |")
    lines += ["", "## B. Pool scaling, causal@5 (n=30 per pool, seed 0)", "", "| pool | PPR alpha 0.85 | PPR alpha 0.95 (tuned) | additive |", "|---|---|---|---|"]
    for pool, r in res["B_scale_tuned_ppr"].items():
        lines.append(f"| {pool} | {r['graph_ppr_a0.85']:.3f} | {r['graph_ppr_a0.95']:.3f} | {r['tcmf_add']:.3f} |")
    lines += ["", "## C. Eight domains, test split (15/domain), causal@5", "", "| domain | tau | additive | mult 0.6 | mult 16 |", "|---|---|---|---|---|"]
    for d, r in res["C_domains_tuned_mult"].items():
        lines.append(f"| {d} | {r['threshold']} | {r['add_l4']:.3f} | {r['mult_l0.6']:.3f} | {r['mult_l16']:.3f} |")
    (OUT / "RESULTS_REVIEWER_N28.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
