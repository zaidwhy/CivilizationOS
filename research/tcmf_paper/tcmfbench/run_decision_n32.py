"""N32: the decision tier with stronger judges.

Every reviewer called the decision test the weakest part: one 3B model, n=60. This reruns the
identical N27 protocol (same 60 real-text scenarios, options, prompt, k=5, clean tau=0.60 and
leaky tau=0.45, arms additive 4 / multiplicative 0.6 and 16 / causal only) plus the no-retrieval
floor and the oracle ceiling, with larger judges from other model families served through
OpenRouter. All paid calls share the TCMF ledger and its cap (``run_llmgraph_n31.TCMF_BUDGET_USD``).

    python -m tcmfbench.run_decision_n32 --judges meta-llama/llama-3.3-70b-instruct google/gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .decision import build_options, build_prompt, is_correct
from .embed_client import EmbedClient
from .openrouter_client import Ledger, OpenRouterClient
from .realtext import RealConfig, generate_many_realtext
from .run_decision_n27 import K, _arms, mcnemar_exact
from .run_llmgraph_n31 import LEDGER, TCMF_BUDGET_USD
from .stats import wilson_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_decision_n32"


def run_judge(judge: str, mats) -> dict:
    llm = OpenRouterClient(judge, OUT / f"cache_{judge.replace('/', '_')}.json",
                           Ledger(LEDGER, TCMF_BUDGET_USD), max_tokens=200)
    out = {}
    try:
        controls = {"no_retrieval": [], "oracle": []}
        for idx, mat in enumerate(mats):
            options, true_index = build_options(mat.scenario.domain, seed=1000 + idx)
            q = mat.scenario.query_text
            controls["no_retrieval"].append(is_correct(llm.chat(build_prompt(q, [], options)), true_index))
            oracle = [mat.mem[i]["text"] for i in sorted(mat.gold_causal)]
            controls["oracle"].append(is_correct(llm.chat(build_prompt(q, oracle, options)), true_index))
        out["controls"] = {k: list(wilson_ci(sum(v), len(v))) for k, v in controls.items()}
        for cond, thr in (("clean", 0.60), ("leaky", 0.45)):
            arms = _arms(thr)
            correct = {k: [] for k in arms}
            for idx, mat in enumerate(mats):
                options, true_index = build_options(mat.scenario.domain, seed=1000 + idx)
                for name, fn in arms.items():
                    texts = [mat.mem[i]["text"] for i in fn(mat)[:K]]
                    correct[name].append(is_correct(llm.chat(build_prompt(mat.scenario.query_text, texts, options)),
                                                    true_index))
                if (idx + 1) % 20 == 0:
                    llm.flush()
                    print(judge, cond, idx + 1, f"spent ${llm.ledger.total:.4f}", flush=True)
            out[cond] = {
                "threshold": thr,
                "acc": {k: list(wilson_ci(sum(v), len(v))) for k, v in correct.items()},
                "correct": {k: [bool(x) for x in v] for k, v in correct.items()},
                "mcnemar_add_vs_mult16": mcnemar_exact(correct["add_l4"], correct["mult_l16"]),
            }
    finally:
        llm.flush()
    return out


def main(judges):
    OUT.mkdir(exist_ok=True)
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    scs = generate_many_realtext(60, RealConfig(n_domains=6), ec, base_seed=0)
    mats = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in scs]
    path = OUT / "results_decision_n32.json"
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for judge in judges:
        res[judge] = run_judge(judge, mats)
        path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = ["# N32: decision accuracy with stronger judges (n=60, k=5, Wilson 95% CI)", "",
             "| judge | no retrieval | oracle | cond | additive 4 | mult 0.6 | mult 16 | causal only | add vs mult16 (discordant, McNemar p) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for judge, r in res.items():
        c = r["controls"]
        for cond in ("clean", "leaky"):
            a = r[cond]["acc"]
            d1, d2, p = r[cond]["mcnemar_add_vs_mult16"]
            lines.append(f"| {judge} | {c['no_retrieval'][0]:.2f} | {c['oracle'][0]:.2f} | {cond} | {a['add_l4'][0]:.2f} | "
                         f"{a['mult_l0.6'][0]:.2f} | {a['mult_l16'][0]:.2f} | {a['causal_only'][0]:.2f} | {d1}/{d2}, p={p:.3f} |")
    (OUT / "RESULTS_DECISION_N32.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", nargs="+", required=True)
    main(ap.parse_args().judges)
