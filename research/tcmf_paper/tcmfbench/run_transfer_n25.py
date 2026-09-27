"""N25: does a multiplicative weight tuned in one setting transfer to settings it was not tuned on?

N24 showed that held-out tuning over a wide enough grid finds a multiplicative weight
(lambda=16) that matches additive fusion on the pure synthetic regime it was tuned on. The
paper's remaining claim is that multiplication's weight cannot be derived in advance, while the
additive weight (lambda=4) follows from the causal margins. This script applies both, unchanged,
to settings neither was tuned on:

  - mixed regime, realistic pool (5 seeds x 300)
  - real text, nomic-embed-text, the six original domains (results_realtext's scenarios)
  - real text, nomic-embed-text, all eight domains (results_encoder2's TEST scenarios)

Offline: real-text embeddings come from the committed caches.

    python -m tcmfbench.run_transfer_n25
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .embed_client import EmbedClient
from .mixed import MixedConfig, generate_many_mixed
from .realtext import RealConfig, generate_many_realtext
from .run_eval import SEED_STRIDE
from .run_realtext import _score as _score_rt
from .stats import bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_transfer"
THR_REAL = 0.60


def _arms(thr):
    return {
        "add_l4": lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=thr, clean=True),
        "mult_l0.6": lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=thr),
        "mult_l8": lambda m: M.rank_tcmf_multiplicative(m, lam=8.0, threshold=thr),
        "mult_l16": lambda m: M.rank_tcmf_multiplicative(m, lam=16.0, threshold=thr),
        "causal_only": lambda m: M.rank_causal_only(m, threshold=thr, clean=True),
    }


def _evaluate(mats, arms) -> dict:
    rows = {k: [] for k in arms}
    for mat in mats:
        for k, fn in arms.items():
            rows[k].append(_score_rt(fn(mat), mat))
    out = {}
    for k, rs in rows.items():
        out[k] = {met: list(bootstrap_ci([r[met] for r in rs]))
                  for met in ("recall@5", "recall@10", "causal@5", "semantic@5", "root_rank")}
    return out


async def main():
    results = {}
    # mixed regime, realistic pool
    mcfg = MixedConfig(n_distractors=20, n_noise=55)
    mixed = [M.materialize(sc, mcfg.max_mem_per_citizen)
             for s in range(5) for sc in generate_many_mixed(300, mcfg, base_seed=s * SEED_STRIDE)]
    results["mixed_pool80"] = {"n": len(mixed), "threshold": 0.45, "arms": _evaluate(mixed, _arms(0.45))}

    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    rt6 = generate_many_realtext(120, RealConfig(n_domains=6), ec, base_seed=0)
    rt6 = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in rt6]
    results["realtext_6dom"] = {"n": len(rt6), "threshold": THR_REAL, "arms": _evaluate(rt6, _arms(THR_REAL))}

    ec2 = EmbedClient(cache_path=ROOT / "results_encoder2" / "emb_cache_nomic.json")
    rt8 = generate_many_realtext(80, RealConfig(), ec2, base_seed=500_000)
    rt8 = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in rt8]
    results["realtext_8dom_test"] = {"n": len(rt8), "threshold": THR_REAL, "arms": _evaluate(rt8, _arms(THR_REAL))}

    # Where Proposition 1(a) predicts a real operator gap: non-gold memories with a partial boost.
    # (1) the leaky synthetic-era threshold 0.45 on real text, which the paper says leaks boosts to
    # distractors; (2) one fabricated direct-cause edge in every mixed-regime scenario (p=1.0).
    results["realtext_6dom_leaky_tau045"] = {"n": len(rt6), "threshold": 0.45, "arms": _evaluate(rt6, _arms(0.45))}
    scfg = MixedConfig(n_distractors=20, n_noise=55, spurious_edge_rate=1.0)
    spur = [M.materialize(sc, scfg.max_mem_per_citizen)
            for s in range(5) for sc in generate_many_mixed(300, scfg, base_seed=s * SEED_STRIDE)]
    results["mixed_pool80_spurious_p1"] = {"n": len(spur), "threshold": 0.45, "arms": _evaluate(spur, _arms(0.45))}

    OUT.mkdir(exist_ok=True)
    (OUT / "results_transfer.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    lines = ["# N25: transfer of a fixed fusion weight to settings it was not tuned on", ""]
    for setting, r in results.items():
        lines += [f"## {setting} (n={r['n']}, threshold={r['threshold']})", "",
                  "| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |", "|---|---|---|---|---|---|"]
        for arm, m in r["arms"].items():
            lines.append(f"| {arm} | " + " | ".join(
                f"{m[k][0]:.3f}" if k != "root_rank" else f"{m[k][0]:.1f}"
                for k in ("recall@5", "recall@10", "causal@5", "semantic@5", "root_rank")) + " |")
        lines.append("")
    (OUT / "RESULTS_TRANSFER.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
