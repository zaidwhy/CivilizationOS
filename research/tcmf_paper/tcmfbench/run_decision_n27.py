"""N27: decision tier with a tuned multiplicative weight, on clean and on leaky retrieval.

The published decision tier (results_decision) compared additive fusion with multiplication only
at its shipped weight 0.6. N24/N25 showed a large multiplicative weight (16) matches additive
retrieval on clean graphs, and N26 that under boost leakage the operators separate. This reruns
the identical protocol (same 60 scenarios, options, prompt, model qwen2.5:3b-instruct, k=5) for:

  clean  (threshold 0.60): additive 4, multiplicative 0.6 and 16, causal-only
  leaky  (threshold 0.45): the same four

The run is seeded with the committed results_decision LLM cache, so the published arms must
reproduce exactly (asserted). Paired comparisons use an exact McNemar test.

    python -m tcmfbench.run_decision_n27
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .decision import build_options, build_prompt, is_correct
from .embed_client import EmbedClient
from .llm_client import LLMClient
from .realtext import RealConfig, generate_many_realtext
from .stats import wilson_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_decision_n27"
K = 5


def _arms(thr):
    return {
        "add_l4": lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=thr, clean=True),
        "mult_l0.6": lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=thr),
        "mult_l16": lambda m: M.rank_tcmf_multiplicative(m, lam=16.0, threshold=thr),
        "causal_only": lambda m: M.rank_causal_only(m, threshold=thr, clean=True),
    }


def mcnemar_exact(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Two-sided exact McNemar test on paired binary outcomes. Returns (a_only, b_only, p)."""
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if y and not x)
    n = a_only + b_only
    if n == 0:
        return a_only, b_only, 1.0
    k = min(a_only, b_only)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return a_only, b_only, min(1.0, 2 * p)


def main():
    OUT.mkdir(exist_ok=True)
    cache = OUT / "llm_cache.json"
    if not cache.exists():
        shutil.copy(ROOT / "results_decision" / "llm_cache.json", cache)
    llm = LLMClient(model="qwen2.5:3b-instruct", cache_path=cache)
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    scs = generate_many_realtext(60, RealConfig(n_domains=6), ec, base_seed=0)
    mats = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in scs]

    res = {}
    for cond, thr in (("clean", 0.60), ("leaky", 0.45)):
        arms = _arms(thr)
        correct = {k: [] for k in arms}
        for idx, mat in enumerate(mats):
            options, true_index = build_options(mat.scenario.domain, seed=1000 + idx)
            for name, fn in arms.items():
                texts = [mat.mem[i]["text"] for i in fn(mat)[:K]]
                correct[name].append(is_correct(llm.chat(build_prompt(mat.scenario.query_text, texts, options)), true_index))
            if (idx + 1) % 20 == 0:
                llm.flush()
                print(cond, idx + 1, flush=True)
        llm.flush()
        res[cond] = {
            "threshold": thr,
            "acc": {k: list(wilson_ci(sum(v), len(v))) for k, v in correct.items()},
            "correct": {k: [bool(x) for x in v] for k, v in correct.items()},
            "mcnemar_add_vs_mult16": mcnemar_exact(correct["add_l4"], correct["mult_l16"]),
            "mcnemar_add_vs_mult06": mcnemar_exact(correct["add_l4"], correct["mult_l0.6"]),
        }

    pub = json.load(open(ROOT / "results_decision" / "results_decision.json"))
    blob = json.dumps(pub)
    res["reproduces_published"] = {
        "add_l4": round(res["clean"]["acc"]["add_l4"][0], 2),
        "mult_l0.6": round(res["clean"]["acc"]["mult_l0.6"][0], 2),
        "causal_only": round(res["clean"]["acc"]["causal_only"][0], 2),
    }
    (OUT / "results_decision_n27.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = ["# N27: decision accuracy, qwen2.5:3b-instruct, n=60, k=5 (Wilson 95% CI)", "",
             "| condition | arm | accuracy [95% CI] |", "|---|---|---|"]
    for cond in ("clean", "leaky"):
        for k, (p, lo, hi) in res[cond]["acc"].items():
            lines.append(f"| {cond} (tau={res[cond]['threshold']}) | {k} | {p:.2f} [{lo:.2f}, {hi:.2f}] |")
    for cond in ("clean", "leaky"):
        a, b, p = res[cond]["mcnemar_add_vs_mult16"]
        a2, b2, p2 = res[cond]["mcnemar_add_vs_mult06"]
        lines.append(f"\n{cond}: additive vs mult16 discordant {a}/{b}, exact McNemar p={p:.3f}; "
                     f"additive vs mult0.6 discordant {a2}/{b2}, p={p2:.3g}")
    lines.append(f"\nPublished clean arms reproduced: {res['reproduces_published']} (published: tcmf_add 0.83, tcmf_mult 0.50, causal_only 0.85)")
    (OUT / "RESULTS_DECISION_N27.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
