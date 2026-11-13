"""Turn Tier A raw rows into tables and the pre-registered paired tests.

    python -m tcmfaudit.analyze_retrieval

Writes ``results/retrieval/SUMMARY.md`` (every cell, every method) and
``results/retrieval/tests.json`` (the registered comparisons).

The registered metric is root_hit@5. Production asks the retriever for 12 memories and shows
the council the first 8, so every table also reports root_hit at 8 and 12 and the reciprocal
rank of the root, all derived from the stored rank. A cutoff-free reading matters here because
the default world has six symptom memories and six unrelated events, both just above five.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict

import numpy as np

from . import AUDIT_ROOT
from .stats import holm, mean_ci, paired_diff

RESULTS = AUDIT_ROOT / "results" / "retrieval"
STORED = ("root_hit", "causal_recall", "symptom_recall", "decoy_in_top", "root_rank",
          "anc_recall", "anc_precision", "pool")
EQUIVALENCE_MARGIN = 0.05

Methods = dict[str, dict[str, np.ndarray]]      # method -> metric -> per-seed values
Table = dict[str, Methods]                      # cell -> Methods


def load(exp: str) -> Table:
    raw: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    with gzip.open(RESULTS / f"{exp}.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            for metric in STORED:
                raw[row["cell"]][row["method"]][metric][row["seed"]] = row[metric]
    table: Table = {}
    for cell, methods in raw.items():
        table[cell] = {}
        for method, metrics in methods.items():
            m = {k: np.array([v[s] for s in sorted(v)], dtype=float) for k, v in metrics.items()}
            m["root_hit8"] = (m["root_rank"] <= 8).astype(float)
            m["root_hit12"] = (m["root_rank"] <= 12).astype(float)
            m["root_mrr"] = 1.0 / m["root_rank"]
            table[cell][method] = m
    return table


def experiments() -> list[str]:
    return sorted(p.name.removesuffix(".jsonl.gz") for p in RESULTS.glob("*.jsonl.gz"))


def cell_table(cell: str, methods: Methods) -> list[str]:
    first = next(iter(methods.values()))
    precision = first["anc_precision"]
    shown = "n/a" if np.all(np.isnan(precision)) else f"{np.nanmean(precision):.2f}"
    lines = [
        f"**{cell}** (n={len(first['root_hit'])}, pool={int(first['pool'][0])}, observed-ancestor "
        f"recall {first['anc_recall'].mean():.2f}, precision {shown})", "",
        "| method | root_hit@5 [95% CI] | @8 | @12 | root MRR | causal recall@5 | symptom recall@5 | unrelated-event memories in top 5 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for method, m in methods.items():
        mean, lo, hi = mean_ci(m["root_hit"])
        lines.append(
            f"| {method} | {mean:.3f} [{lo:.3f}, {hi:.3f}] | {m['root_hit8'].mean():.3f} | "
            f"{m['root_hit12'].mean():.3f} | {m['root_mrr'].mean():.3f} | {m['causal_recall'].mean():.3f} | "
            f"{m['symptom_recall'].mean():.3f} | {m['decoy_in_top'].mean():.2f} |")
    return lines + [""]


def registered_tests(tables: dict[str, Table]) -> dict[str, dict]:
    """The comparisons PREREG.md commits to, plus the same pairs at k = 8 and on MRR.

    Holm is applied to the registered root_hit@5 family only. ``verdict`` applies the
    registered decision rule: the difference and its interval against the 0.05 margin.
    """
    pairs: list[tuple[str, str, str, str, str, str]] = [
        ("H1", "paper condition (chain-only graph)", "A0_controls", "paper_condition", "tcmf_deployed", "graph_union"),
        ("H1", "perfect graph, other events present", "A1_oracle", "oracle", "tcmf_deployed", "graph_union"),
    ]
    for rho in (0.0, 0.5):
        cell = f"deployed|root_age=60-150|rho={rho}"
        pairs.append(("H2", f"deployed linker, {cell}", "A3_deployed_graph", cell, "tcmf_deployed", "vector"))
    for rho in (0.2, 0.4, 0.6, 0.8):
        cell = f"rho={rho}|rho_decoy=same|noisy"
        pairs.append(("H4", cell, "A4_rho", cell, "tcmf_deployed", "vector"))
    for cell in tables["A7_ablation"]:
        pairs.append(("H6", f"no recency vs full, {cell}", "A7_ablation", cell, "no_recency", "full_reimpl"))

    tests: dict[str, dict] = {}
    for hyp, label, exp, cell, a, b in pairs:
        ma, mb = tables[exp][cell][a], tables[exp][cell][b]
        tests[f"{hyp} | {a} - {b} | {label}"] = _compare(hyp, ma, mb)
    for depth in (1, 2, 3):   # H3 compares the same retriever across two graphs of the same worlds
        ma = tables["A2_depth"][f"depth={depth}|oracle"]["tcmf_deployed"]
        mb = tables["A2_depth"][f"depth={depth}|chain_only"]["tcmf_deployed"]
        tests[f"H3 | tcmf_deployed: other events present - chain only | depth={depth}"] = _compare("H3", ma, mb)

    adjusted = holm({k: v["root_hit"]["p"] for k, v in tests.items()})
    for key, p in adjusted.items():
        tests[key]["root_hit"]["p_holm"] = p
    return tests


def _compare(hyp: str, ma: dict[str, np.ndarray], mb: dict[str, np.ndarray]) -> dict:
    out: dict = {"hypothesis": hyp}
    for metric in ("root_hit", "root_hit8", "root_hit12", "root_mrr"):
        out[metric] = {"a": float(ma[metric].mean()), "b": float(mb[metric].mean()),
                       **paired_diff(ma[metric], mb[metric])}
        out[metric]["identical_on_every_scenario"] = bool(np.array_equal(ma[metric], mb[metric]))
    d = out["root_hit"]
    if d["lo"] > EQUIVALENCE_MARGIN:
        out["verdict_at_5"] = "first arm better by more than the margin"
    elif d["hi"] < -EQUIVALENCE_MARGIN:
        out["verdict_at_5"] = "first arm worse by more than the margin"
    elif -EQUIVALENCE_MARGIN < d["lo"] and d["hi"] < EQUIVALENCE_MARGIN:
        out["verdict_at_5"] = "within the margin"
    else:
        out["verdict_at_5"] = "inconclusive against the margin"
    return out


def main() -> None:
    tables = {exp: load(exp) for exp in experiments()}
    lines = ["# Tier A raw summary", "",
             "Generated by `python -m tcmfaudit.analyze_retrieval` from the `*.jsonl.gz` rows beside "
             "this file. Intervals are percentile bootstrap, 5000 resamples. Experiments prefixed "
             "`P` were added after the first run and `R` after independent review; see PREREG.md.", ""]
    for exp, table in tables.items():
        lines += [f"## {exp}", ""]
        for cell, methods in table.items():
            lines += cell_table(cell, methods)
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

    tests = registered_tests(tables)
    (RESULTS / "tests.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
    print(f"{'registered comparison':<88} {'@5 a':>6} {'b':>6} {'diff [95% CI]':>24} {'Holm p':>7} {'@8 diff':>8} {'MRR diff':>9}")
    for key, t in tests.items():
        d = t["root_hit"]
        print(f"{key[:88]:<88} {d['a']:6.3f} {d['b']:6.3f} {d['diff']:+7.3f} [{d['lo']:+.3f},{d['hi']:+.3f}] "
              f"{d['p_holm']:7.4f} {t['root_hit8']['diff']:+8.3f} {t['root_mrr']['diff']:+9.3f}")


if __name__ == "__main__":
    main()
