"""N30 addendum: does the weight the additive bound predicts restore parity on the clean shapes
where lambda=4 falls short?

On the clean six-event chain and the side-cause shape (proximate weights), lambda=4 clears the
additive bound in only 10% and 78% of scenarios, and addition trails multiplication at its tuned
lambda=16. The bound's 95th percentile is 5.35 and 4.28 there, so lambda=6 is predicted to suffice
without tuning. This reruns the same 600 scenarios per shape, with N30's scoring and depth cap, at
lambda=6; lambda=4 and the multiplicative lambda=16 are recomputed as a check against N30.

    python -m tcmfbench.run_structures_n30_lambda6
"""
from __future__ import annotations

import json

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .run_structures_n30 import BFS_CAP, OUT, PER_SEED, SEEDS, _build, _rank

SHAPES = ("chain6", "side_cause")


def main():
    n30 = json.loads((OUT / "results_structures_n30.json").read_text(encoding="utf-8"))["families"]
    res = {}
    for shape in SHAPES:
        out = {"add_l4": [], "add_l6": [], "mult_l16": []}
        for s in range(SEEDS):
            for i in range(PER_SEED):
                mat = _build(shape, "clean", s, i)
                ids = list(mat.all_ids)
                e_d = M._episodic_scores(mat)
                b_d = M._causal_boosts(mat, 0.45, clean=True, favor_root=False, bfs_depth_cap=BFS_CAP)
                e = np.array([e_d[x] for x in ids])
                eh_d = M._minmax(e_d)
                eh = np.array([eh_d[x] for x in ids])
                b = np.array([b_d[x] for x in ids])
                for name, score in (("add_l4", eh + 4 * b), ("add_l6", eh + 6 * b),
                                    ("mult_l16", e * (1 + 16 * b))):
                    out[name].append(MT.recall_at_k(_rank(ids, score), mat.gold_ids, 5))
        v = {k: float(np.mean(x)) for k, x in out.items()}
        ref = n30[f"{shape}_clean_prox"]
        assert abs(v["add_l4"] - ref["add_l4"]) < 1e-12 and abs(v["mult_l16"] - ref["mult_l16"]) < 1e-12, shape
        v.update(n=len(out["add_l4"]), need_add_p95=ref["need_add_p95"], frac_add4_suffices=ref["frac_add4_suffices"])
        res[f"{shape}_clean_prox"] = v
        print(shape, {k: round(x, 4) if isinstance(x, float) else x for k, x in v.items()}, flush=True)
    (OUT / "results_structures_n30_lambda6.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
