"""Audit L1: recompute every cell of the long SRW paper's Tables 2 (tab:leak), 5 (tab:llm) and
6 (tab:judges), and of the 4-page cut's leak table, from the raw result files with one rounding
rule, and flag exact ties.

Rounding rule (stated in the paper's appendix): each stored value is first rounded to 9 decimals
to strip binary floating-point noise (0.6249999999999998 is the fraction 75/120 = 0.625), then
rounded half up (ties away from zero) to the printed precision. Python's round() rounds half to
even on the binary value and would print some exact ties differently, so it is not used.

    python research/tcmf_paper/recompute_rounding_l1.py      (from the repo root, any venv)
"""
from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TIES: list[tuple[str, Decimal, Decimal, Decimal]] = []


def fmt(x: float, places: int = 2, where: str = "") -> str:
    d = Decimal(f"{x:.9f}")
    q = Decimal(1).scaleb(-places)
    up, even = d.quantize(q, ROUND_HALF_UP), d.quantize(q, ROUND_HALF_EVEN)
    if up != even:
        TIES.append((where, d.normalize(), up, even))
    return str(up)


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def table_leak() -> list[str]:
    n28 = load("results_reviewer_n28/results_reviewer_n28.json")["A_leakage_isolation"]
    lk = load("results_leakage/results_leakage.json")
    rows = [("none", "spurious_p0.0", ("spurious", "0.0")),
            ("on-topic, p=0.5", "spurious_p0.5", ("spurious", "0.5")),
            ("on-topic, p=1", "spurious_p1.0", ("spurious", "1.0")),
            ("on-topic, text tau=0.45", "realtext_tau0.45", ("realtext", "0.45")),
            ("none, text tau=0.60", "realtext_tau0.6", ("realtext", "0.6"))]
    out = []
    for label, key, (tier, p) in rows:
        cells = []
        for tag in ("prox", "root"):
            v = n28[f"{key}_{tag}"]
            best_raw = max(v["best_mult_raw"]["recall@5"], v["mult_raw_limit"])
            best_norm = max(v["best_mult_norm"]["recall@5"], v["mult_norm_limit"])
            causal = lk[tier][p]["arms"][f"causal_only_{tag}"]["recall@5"][0]
            for name, x in (("+", v["add_norm_l4"]), ("best x raw", best_raw),
                            ("best x norm", best_norm), ("causal", causal)):
                cells.append(fmt(x, 2, f"tab:leak {label} {tag} {name}"))
        out.append(f"{label:26s} & " + " & ".join(cells))
    return out


def table_llm() -> list[str]:
    a = load("results_llmgraph_n31/results_llmgraph_n31.json")
    b = load("results_llmgraph_n31/results_llmgraph_n31b.json")["graphs"]
    models = [("Llama-3.3-70B", "meta-llama/llama-3.3-70b-instruct"),
              ("Gemini-2.5-Flash", "google/gemini-2.5-flash"),
              ("Mistral-7B", "mistral:7b"), ("Qwen2.5-3B", "qwen2.5:3b-instruct")]
    out = []

    def pair(v, where):
        return fmt(v["add_l4"], 2, where + " add") + " / " + fmt(v["mult_l16"], 2, where + " mult")

    cells = ["1.00", "1.00", "0.0"]
    for tag in ("prox", "root"):
        cells.append(pair(a["reference"][f"true_{tag}"], f"tab:llm true chain original {tag}"))
    for tag in ("prox", "root"):
        cells.append(pair(b[f"true chain|{tag}"], f"tab:llm true chain +bg {tag}"))
    out.append("true chain       & " + " & ".join(cells))
    for label, mid in models:
        m = a["models"][mid]
        safe = mid.replace(":", "_").replace("/", "_")
        cells = [fmt(m["ancestor_precision"], 2, f"tab:llm {label} precision"),
                 fmt(m["ancestor_recall"], 2, f"tab:llm {label} recall"),
                 fmt(m["false_ancestors_mean"], 1, f"tab:llm {label} false/scen")]
        for tag in ("prox", "root"):
            cells.append(pair(m[f"retrieval_{tag}"], f"tab:llm {label} original {tag}"))
        for tag in ("prox", "root"):
            cells.append(pair(b[f"{safe}|{tag}"], f"tab:llm {label} +bg {tag}"))
        out.append(f"{label:16s} & " + " & ".join(cells))
    return out


def table_judges() -> list[str]:
    d = load("results_decision_n34/results_decision_n34.json")
    judges = [("Qwen2.5-3B", "qwen2.5:3b-instruct"), ("Llama-3.3-70B", "meta-llama/llama-3.3-70b-instruct"),
              ("Gemini-2.5-Flash", "google/gemini-2.5-flash")]
    out = []
    for label, j in judges:
        r = d[j]
        w = "tab:judges " + label
        c = r["controls"]
        cells = [fmt(c["no_retrieval"][0], 2, w + " none") + " / " + fmt(c["oracle"][0], 2, w + " oracle")]
        for cond in ("clean", "leaky"):
            acc = r[cond]["acc"]
            cells.append(fmt(acc["add_l4"][0], 2, w + " " + cond + " add") + " / "
                         + fmt(acc["mult_l16"][0], 2, w + " " + cond + " mult"))
        out.append(f"{label:17s} & " + " & ".join(cells))
    return out


def table_leak_short() -> list[str]:
    """main_srw.tex tab:leak: proximate weights; best x = max over raw, normalized and limits."""
    n28 = load("results_reviewer_n28/results_reviewer_n28.json")["A_leakage_isolation"]
    lk = load("results_leakage/results_leakage.json")
    cl = load("results_clutter_n29/results_clutter_n29.json")["synthetic"]
    out = []
    for label, key, (tier, p) in (("none", "spurious_p0.0", ("spurious", "0.0")),
                                  ("on-topic, p=0.5", "spurious_p0.5", ("spurious", "0.5")),
                                  ("on-topic, p=1", "spurious_p1.0", ("spurious", "1.0")),
                                  ("on-topic, text tau=0.45", "realtext_tau0.45", ("realtext", "0.45"))):
        v = n28[f"{key}_prox"]
        best = max(v["best_mult_raw"]["recall@5"], v["mult_raw_limit"],
                   v["best_mult_norm"]["recall@5"], v["mult_norm_limit"])
        causal = lk[tier][p]["arms"]["causal_only_prox"]["recall@5"][0]
        w = "short tab:leak " + label
        out.append(f"{label:26s} & " + " & ".join(
            [fmt(v["add_norm_l4"], 2, w + " +"), fmt(v["means"]["mult_raw_l16"], 2, w + " x16"),
             fmt(best, 2, w + " best x"), fmt(causal, 2, w + " causal")]))
    for k in (1, 4, 8):
        v = cl[f"bg16_k{k}_prox"]
        w = f"short tab:leak clutter k={k}"
        out.append(f"clutter, k={k}{'':15s} & " + " & ".join(
            [fmt(v["add_l4"], 2, w + " +"), fmt(v["mult_raw_l16"], 2, w + " x16"),
             fmt(v["best_mult"], 2, w + " best x"), fmt(v["causal"], 2, w + " causal")]))
    return out


def main():
    for name, fn in (("Table 2 (tab:leak)", table_leak), ("Table 5 (tab:llm)", table_llm),
                     ("Table 6 (tab:judges)", table_judges),
                     ("4-page cut, tab:leak", table_leak_short)):
        print("== " + name)
        for row in fn():
            print(row)
    print("== exact ties at the printed precision (half up and half to even differ):")
    for where, exact, up, even in TIES:
        print("  {}: exact {}, half up {}, half to even {}".format(where, exact, up, even))


if __name__ == "__main__":
    main()
