"""N21: is the shipped retriever's lower recall@5 (0.79) due to favor-root depth weighting, or to
its deployed lambda=2.0 sitting below the Corollary bound (3.32-3.64)? Runs the REAL retriever
(additive + favor-root) at lambda 2, 4, 8 on the realistic pure pool, 5 seeds x 300."""
from __future__ import annotations
import asyncio, json
from pathlib import Path
import numpy as np
from . import _bootstrap  # noqa: F401
from .generator import GenConfig
from . import methods as M
from .run_eval import _materialize, _eval_methods_raw, _agg, SEED_STRIDE

OUT = Path(__file__).resolve().parents[1] / "results_shipped_lambda"
LAMS = [2.0, 4.0, 8.0]


async def main(n=300, seeds=(0, 1, 2, 3, 4)):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    fns = {f"shipped_l{l:g}": (lambda m, l=l: M.rank_tcmf(m, lam=l)) for l in LAMS}
    fns["additive_l4"] = lambda m: M.rank_tcmf_additive(m, lam=4.0)
    rows = {k: [] for k in fns}
    for s in seeds:
        mats = _materialize(cfg, n, s * SEED_STRIDE)
        per = await _eval_methods_raw(mats, fns)
        for k in fns:
            rows[k] += per[k]
    res = {k: {m: list(v) for m, v in _agg(r).items()} for k, r in rows.items()}
    OUT.mkdir(exist_ok=True)
    json.dump({"n": n * len(seeds), "seeds": list(seeds), "pool": 78, "results": res},
              open(OUT / "results_shipped_lambda.json", "w"), indent=1)
    lines = ["# N21: shipped retriever (additive + favor-root) vs lambda, pure regime, pool 78, "
             f"n={n*len(seeds)}", "", "| method | recall@5 | recall@10 | root_rank | root_mrr |",
             "|---|---|---|---|---|"]
    for k, r in res.items():
        f = lambda m: f"{r[m][0]:.3f} [{r[m][1]:.3f},{r[m][2]:.3f}]"
        lines.append(f"| {k} | {f('recall@5')} | {f('recall@10')} | {r['root_rank'][0]:.2f} | {r['root_mrr'][0]:.3f} |")
    (OUT / "RESULTS_SHIPPED_LAMBDA.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
