"""N26b: the mechanism behind N26's operator gap, measured on every causal-gold memory.

N26's per-scenario check looked only at the root cause and found the multiplicative-only
unreachable region rare there. The gap is in causal@5, which counts all three causal-gold
memories, so this counts (causal-gold i, non-gold j) pairs where j carries a leaked boost:

  - mult-only unreachable: 0 < b_j < b_i and e_i/e_j <= b_j/b_i  (Proposition 1(a): no
    multiplicative weight ranks i above j, but additive does once lambda > 1/(b_i - b_j));
  - unreachable for both:  b_j >= b_i                            (no operator can fix);
  - reachable for both:    every other leaked pair.

    python -m tcmfbench.run_leakage_mechanism_n26b
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .embed_client import EmbedClient
from .mixed import MixedConfig, generate_many_mixed
from .realtext import RealConfig, generate_many_realtext
from .run_eval import SEED_STRIDE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_leakage"


def _pairs(mats, thr, fr) -> dict:
    mult_only = both = reachable = 0
    for mat in mats:
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
        gold_causal = getattr(mat, "gold_causal", None) or {mat.root_id}
        for i in gold_causal:
            for j in mat.all_ids:
                if j in mat.gold_ids or b[j] <= 0:
                    continue
                if b[j] >= b[i]:
                    both += 1
                elif e[i] < e[j] and e[i] / e[j] <= b[j] / b[i]:
                    mult_only += 1
                else:
                    reachable += 1
    tot = mult_only + both + reachable
    return {"leaked_pairs": tot,
            "frac_mult_only_unreachable": mult_only / tot if tot else 0.0,
            "frac_unreachable_for_both": both / tot if tot else 0.0,
            "frac_reachable_for_both": reachable / tot if tot else 0.0}


def _limit_recall5(mats, thr, fr) -> float:
    """recall@5 of multiplicative fusion in the limit lambda -> infinity: rank by e*b, ties
    (b = 0) by e. This is the best any multiplicative weight can approach."""
    from .run_realtext import _score
    vals = []
    for mat in mats:
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
        ranked = sorted(mat.all_ids, key=lambda i: (e[i] * b[i], e[i]), reverse=True)
        vals.append(_score(ranked, mat)["recall@5"])
    return sum(vals) / len(vals)


def main():
    res = {}
    for p in (0.1, 0.25, 0.5, 1.0):
        cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=p)
        mats = [M.materialize(sc, cfg.max_mem_per_citizen)
                for s in range(5) for sc in generate_many_mixed(300, cfg, base_seed=s * SEED_STRIDE)]
        res[f"spurious_p{p}"] = {tag: dict(_pairs(mats, 0.45, fr), mult_limit_recall5=_limit_recall5(mats, 0.45, fr))
                                 for fr, tag in ((False, "prox"), (True, "root"))}
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    rt = [M.materialize(sc, RealConfig().max_mem_per_citizen)
          for sc in generate_many_realtext(120, RealConfig(n_domains=6), ec, base_seed=0)]
    for tau in (0.45, 0.5):
        res[f"realtext_tau{tau}"] = {tag: dict(_pairs(rt, tau, fr), mult_limit_recall5=_limit_recall5(rt, tau, fr))
                                     for fr, tag in ((False, "prox"), (True, "root"))}
    OUT.mkdir(exist_ok=True)
    (OUT / "results_leakage_mechanism.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = ["# N26b: leaked (causal-gold, non-gold) pairs by reachability", "",
             "| setting | depth weights | leaked pairs | mult-only unreachable | both unreachable | reachable | mult recall@5 as lambda -> inf |",
             "|---|---|---|---|---|---|---|"]
    for s, d in res.items():
        for tag, v in d.items():
            lines.append(f"| {s} | {tag} | {v['leaked_pairs']} | {v['frac_mult_only_unreachable']:.3f} | "
                         f"{v['frac_unreachable_for_both']:.3f} | {v['frac_reachable_for_both']:.3f} | {v['mult_limit_recall5']:.3f} |")
    (OUT / "RESULTS_LEAKAGE_MECHANISM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
