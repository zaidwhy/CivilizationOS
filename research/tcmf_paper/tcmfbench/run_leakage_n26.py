"""N26: when does the fusion OPERATOR (not just the weight) decide? Boost leakage, stress-tested.

N25 found that on clean graphs a large multiplicative weight matches additive fusion, but with a
fabricated causal edge multiplication recovers ~no causal evidence at any weight. Before that
becomes a headline, this script checks it the way a reviewer would:

  1. operator vs depth weighting: both operators under favor-proximate AND favor-root weights;
  2. dose-response: fraction of scenarios with a false edge, p in {0, 0.1, 0.25, 0.5, 1.0};
  3. mechanism: share of scenarios with a non-gold memory j that is additive-reachable but
     multiplicative-unreachable (0 < b_j < b_root and rho < b_j / b_root, Proposition 1(a)),
     versus unreachable for both (b_j >= b_root);
  4. weight robustness: additive lambda in {2, 4, 8, 16}, multiplicative in {0.6, 8, 16, 32};
  5. graded leakage on real text: similarity threshold tau in {0.45, 0.50, 0.55, 0.60}.

Mixed regime, realistic pool (20 distractors, 55 noise), 5 seeds x 300. Offline.

    python -m tcmfbench.run_leakage_n26
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from .embed_client import EmbedClient
from .mixed import MixedConfig, generate_many_mixed
from .realtext import RealConfig, generate_many_realtext
from .run_eval import SEED_STRIDE
from .run_realtext import _score
from .stats import bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_leakage"
RATES = [0.0, 0.1, 0.25, 0.5, 1.0]
TAUS = [0.45, 0.50, 0.55, 0.60]


def _mult(lam, thr, fr):
    def f(mat):
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
        return sorted(mat.all_ids, key=lambda i: e[i] * (1.0 + lam * b[i]), reverse=True)
    return f


def _add(lam, thr, fr):
    return lambda mat: M.rank_tcmf_additive(mat, lam=lam, threshold=thr, clean=True, favor_root=fr)


def _arms(thr):
    arms = {}
    for fr, tag in ((False, "prox"), (True, "root")):
        for lam in (2.0, 4.0, 8.0, 16.0):
            arms[f"add_l{lam:g}_{tag}"] = _add(lam, thr, fr)
        for lam in (0.6, 8.0, 16.0, 32.0):
            arms[f"mult_l{lam:g}_{tag}"] = _mult(lam, thr, fr)
        arms[f"causal_only_{tag}"] = (lambda mat, fr=fr: sorted(
            mat.all_ids, key=M._causal_boosts(mat, thr, clean=True, favor_root=fr).get, reverse=True))
    return arms


def _mechanism(mats, thr, fr) -> dict:
    """Per scenario: does some non-gold j fall in the mult-only-unreachable region?"""
    mult_only = both = 0
    for mat in mats:
        e = M._episodic_scores(mat)
        b = M._causal_boosts(mat, thr, clean=True, favor_root=fr)
        r = mat.root_id
        mo = bo = False
        for j in mat.all_ids:
            if j in mat.gold_ids:
                continue
            if b[j] >= b[r] and b[j] > 0:
                bo = True
            elif 0 < b[j] < b[r] and e[r] < e[j] and e[r] / e[j] <= b[j] / b[r]:
                mo = True
        mult_only += mo
        both += bo
    n = len(mats)
    return {"frac_mult_only_unreachable": mult_only / n, "frac_unreachable_for_both": both / n}


def _eval(mats, arms) -> dict:
    rows = {k: [] for k in arms}
    for mat in mats:
        for k, fn in arms.items():
            rows[k].append(_score(fn(mat), mat))
    return {k: {m: list(bootstrap_ci([r[m] for r in rs])) for m in ("recall@5", "causal@5", "semantic@5", "root_rank")}
            for k, rs in rows.items()}


def main():
    res = {"spurious": {}, "realtext": {}}
    for p in RATES:
        cfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=p)
        mats = [M.materialize(sc, cfg.max_mem_per_citizen)
                for s in range(5) for sc in generate_many_mixed(300, cfg, base_seed=s * SEED_STRIDE)]
        res["spurious"][str(p)] = {
            "n": len(mats), "arms": _eval(mats, _arms(0.45)),
            "mechanism": {tag: _mechanism(mats, 0.45, fr) for fr, tag in ((False, "prox"), (True, "root"))},
        }
        print("spurious", p, "done", flush=True)
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    rt = [M.materialize(sc, RealConfig().max_mem_per_citizen)
          for sc in generate_many_realtext(120, RealConfig(n_domains=6), ec, base_seed=0)]
    for tau in TAUS:
        res["realtext"][str(tau)] = {
            "n": len(rt), "arms": _eval(rt, _arms(tau)),
            "mechanism": {tag: _mechanism(rt, tau, fr) for fr, tag in ((False, "prox"), (True, "root"))},
        }
        print("realtext", tau, "done", flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "results_leakage.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    def block(title, d, key):
        lines = [f"## {title}", "", "| setting | " + " | ".join(ARMS_SHOWN) + " | mult-only unreachable (prox/root) | both unreachable (prox/root) |",
                 "|---|" + "---|" * (len(ARMS_SHOWN) + 2)]
        for s, r in d.items():
            a = r["arms"]; mech = r["mechanism"]
            lines.append(f"| {key}={s} | " + " | ".join(f"{a[k]['causal@5'][0]:.3f}" for k in ARMS_SHOWN)
                         + f" | {mech['prox']['frac_mult_only_unreachable']:.3f} / {mech['root']['frac_mult_only_unreachable']:.3f}"
                         + f" | {mech['prox']['frac_unreachable_for_both']:.3f} / {mech['root']['frac_unreachable_for_both']:.3f} |")
        return lines

    ARMS_SHOWN = ["add_l4_prox", "mult_l16_prox", "mult_l32_prox", "causal_only_prox",
                  "add_l4_root", "mult_l16_root", "mult_l32_root", "causal_only_root"]
    lines = ["# N26: boost leakage - causal@5 by operator, weight and depth weighting", ""]
    lines += block("False direct-cause edge in a fraction p of mixed-regime scenarios (pool 80, n=1500)", res["spurious"], "p")
    lines += [""] + block("Real text, six domains (n=120), similarity threshold tau", res["realtext"], "tau")
    lines += ["", "Full arm grid (additive lambda 2/4/8/16, multiplicative 0.6/8/16/32, both depth weightings) "
              "with recall@5, semantic@5 and root rank is in results_leakage.json."]
    (OUT / "RESULTS_LEAKAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
