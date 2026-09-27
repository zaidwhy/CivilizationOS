"""N24: rerun N03's held-out tuning with grids that do not stop at a winner's edge.

N03's grids let three operators select a value on the boundary of their grid: tcmf_mult
lambda=2.4 (its maximum; the additive grid went up to 8), graph_ppr alpha=0.95 (maximum) and
tcmf_rrf c=2 (minimum). A boundary selection means the baseline may be under-tuned. This script
keeps N03's protocol exactly (same TUNE/TEST seeds, same 5-candidate budget, same selection rule)
and only widens those three grids so each can select an interior value.

    python -m tcmfbench.run_tuned_wide_n24 --regime pure  --out results_main_tuned_wide
    python -m tcmfbench.run_tuned_wide_n24 --regime mixed --out results_mixed_tuned_wide
"""
from __future__ import annotations

import asyncio

from . import _bootstrap  # noqa: F401
from . import run_tuned

WIDE_GRIDS = {
    "tcmf_mult_lambda": [0.6, 2.4, 8.0, 16.0, 32.0],
    "graph_ppr_alpha":  [0.85, 0.95, 0.98, 0.99, 0.995],
    "rrf_c":            [0.1, 0.25, 0.5, 1.0, 2.0],
}

if __name__ == "__main__":
    run_tuned.GRIDS.update(WIDE_GRIDS)
    for name, grid in run_tuned.GRIDS.items():
        assert len(grid) == run_tuned.SWEEP_BUDGET, name
    args = run_tuned.parse_args()
    asyncio.run(run_tuned.run_regime(args.regime, args))
