"""Fig 7: where leaked pairs land in the (rho, beta) plane, against the propositions' boundaries.

Reads results_structures_n30/results_structures_n30.json (N30 part B). Each point is a leaked pair
(i causal-gold, j non-gold with b_j > 0): rho = e_i/e_j, beta = b_j/b_i. In the limit of large
weight, multiplication orders a pair correctly iff rho > beta, addition iff beta < 1.

    python figures/make_fig7_phase.py --out figures [--srw paper/srw/figs]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# TrueType (Type 42) fonts: the default Type 3 fonts trip ACL's font checks.
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figures")
    ap.add_argument("--srw", default=None)
    args = ap.parse_args()
    d = json.load(open(ROOT / "results_structures_n30" / "results_structures_n30.json"))["pairs"]
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    lo, hi = 0.1, 5
    styles = {"onleak": ("on-topic leak", "#c0392b", "o"), "clutter": ("clutter (off-topic)", "#2471a3", "s")}
    for cond, (label, color, marker) in styles.items():
        p = np.clip(np.array(d[cond]["sample"])[:1500], lo, hi)
        ax.scatter(p[:, 0], p[:, 1], s=4, alpha=0.35, color=color, marker=marker, label=label, linewidths=0)
    x = np.array([lo, hi])
    ax.plot(x, x, color="k", lw=1)
    ax.axhline(1, color="k", lw=1, ls="--")
    ax.axvline(1, color="0.6", lw=0.8, ls=":")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ticks = [0.1, 0.25, 0.5, 1, 2, 4]
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        axis.set_major_formatter(matplotlib.ticker.FixedFormatter([f"{t:g}" for t in ticks]))
        axis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel(r"$\rho = e_i/e_j$  (causal vs. leaked memory, episodic)")
    ax.set_ylabel(r"$\beta = b_j/b_i$  (leaked vs. causal boost)")
    kw = dict(fontsize=7, ha="center", va="center")
    ax.text(0.16, 0.45, "only $\\times$ fails\n(Prop. 1)", **kw)
    ax.text(2.6, 0.16, "both succeed", **kw)
    ax.text(0.2, 3.3, "both fail", **kw)
    ax.text(3.4, 1.9, "only $+$ fails\n(Prop. 3)", **kw)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=7, markerscale=3, frameon=False)
    fig.tight_layout()
    for out in [args.out] + ([args.srw] if args.srw else []):
        Path(out).mkdir(parents=True, exist_ok=True)
        name = "fig7_phase" if out == args.out else "fig_phase"
        fig.savefig(Path(out) / f"{name}.pdf")
        fig.savefig(Path(out) / f"{name}.png", dpi=150)
    print("saved")


if __name__ == "__main__":
    main()
