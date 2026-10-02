"""N34: the decision tests at n=120 instead of 60.

Reviewers' most likely objection to the decision tier is its size (n=60). The real-text tier and
N31's LLM-built graphs both have 120 scenarios, so this reruns, unchanged, on all 120:

  A. the N27/N32 protocol (clean tau=0.60 / leaky tau=0.45; additive 4, multiplicative 0.6 and 16,
     causal only; no-retrieval floor and oracle) for all three judges;
  B. the N33 protocol (true chain vs Llama-70B / Gemini-Flash graphs, both operators, both depth
     weightings, one memory per background event) for all three judges.

Caches are seeded from N27/N32/N33 and results_decision, so the first 60 scenarios cost nothing and
must reproduce the published n=60 numbers (asserted). Paid calls share the TCMF ledger, capped for
this run at +$0.45 over the spend recorded when it starts.

    python -m tcmfbench.run_decision_n34 --part A
    python -m tcmfbench.run_decision_n34 --part B
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import run_decision_n33 as D33
from .decision import build_options, build_prompt, is_correct
from .embed_client import EmbedClient
from .llm_client import LLMClient
from .openrouter_client import Ledger, OpenRouterClient
from .realtext import RealConfig, generate_many_realtext
from .run_decision_n27 import K, _arms, mcnemar_exact
from .run_llmgraph_n31 import LEDGER
from .stats import wilson_ci

ROOT = Path(__file__).resolve().parents[1]
OUT_A = ROOT / "results_decision_n34"
OUT_B = ROOT / "results_decision_n34b"
N = 120
JUDGES = ["qwen2.5:3b-instruct", "meta-llama/llama-3.3-70b-instruct", "google/gemini-2.5-flash"]
RUN_CAP_USD = 0.45


def _cap() -> float:
    start = json.loads(Path(LEDGER).read_text(encoding="utf-8"))["total_usd"]
    return start + RUN_CAP_USD


def _merge_caches(dst: Path, srcs: list[Path]) -> None:
    merged = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    for s in srcs:
        if s.exists():
            merged.update(json.loads(s.read_text(encoding="utf-8")))
    dst.write_text(json.dumps(merged), encoding="utf-8")


class _Retry:
    """Retry a chat call on network errors (a timed-out request is not charged and not cached)."""

    def __init__(self, inner, tries: int = 5):
        self.inner, self.tries = inner, tries

    def chat(self, prompt):
        import time
        for k in range(self.tries):
            try:
                return self.inner.chat(prompt)
            except (TimeoutError, OSError) as e:
                if k == self.tries - 1:
                    raise
                print("retry after", type(e).__name__, flush=True)
                time.sleep(5 * (k + 1))

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _client(judge: str, out: Path, cap: float):
    if "/" in judge:
        return _Retry(OpenRouterClient(judge, out / f"cache_{judge.replace('/', '_')}.json",
                                       Ledger(LEDGER, cap), max_tokens=200))
    return _Retry(LLMClient(model=judge, host="http://127.0.0.1:11434", cache_path=out / "llm_cache.json",
                            timeout=300.0))


def part_a(cap: float):
    OUT_A.mkdir(exist_ok=True)
    _merge_caches(OUT_A / "llm_cache.json", [ROOT / "results_decision" / "llm_cache.json",
                                             ROOT / "results_decision_n27" / "llm_cache.json"])
    for j in JUDGES[1:]:
        name = f"cache_{j.replace('/', '_')}.json"
        _merge_caches(OUT_A / name, [ROOT / "results_decision_n32" / name])
    ec = EmbedClient(cache_path=ROOT / "results_realtext" / "emb_cache.json")
    scs = generate_many_realtext(N, RealConfig(n_domains=6), ec, base_seed=0)
    mats = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in scs]
    path = OUT_A / "results_decision_n34.json"
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for judge in JUDGES:
        llm = _client(judge, OUT_A, cap)
        out = {}
        try:
            ctrl = {"no_retrieval": [], "oracle": []}
            for idx, mat in enumerate(mats):
                options, ti = build_options(mat.scenario.domain, seed=1000 + idx)
                q = mat.scenario.query_text
                ctrl["no_retrieval"].append(is_correct(llm.chat(build_prompt(q, [], options)), ti))
                oracle = [mat.mem[i]["text"] for i in sorted(mat.gold_causal)]
                ctrl["oracle"].append(is_correct(llm.chat(build_prompt(q, oracle, options)), ti))
            out["controls"] = {k: list(wilson_ci(sum(v), len(v))) for k, v in ctrl.items()}
            out["controls_correct"] = {k: [bool(x) for x in v] for k, v in ctrl.items()}
            for cond, thr in (("clean", 0.60), ("leaky", 0.45)):
                arms = _arms(thr)
                correct = {k: [] for k in arms}
                for idx, mat in enumerate(mats):
                    options, ti = build_options(mat.scenario.domain, seed=1000 + idx)
                    for name, fn in arms.items():
                        texts = [mat.mem[i]["text"] for i in fn(mat)[:K]]
                        correct[name].append(is_correct(llm.chat(build_prompt(mat.scenario.query_text, texts,
                                                                              options)), ti))
                    if (idx + 1) % 20 == 0:
                        llm.flush()
                        print(judge, cond, idx + 1, flush=True)
                out[cond] = {
                    "threshold": thr,
                    "acc": {k: list(wilson_ci(sum(v), len(v))) for k, v in correct.items()},
                    "correct": {k: [bool(x) for x in v] for k, v in correct.items()},
                    "mcnemar_add_vs_mult16": mcnemar_exact(correct["add_l4"], correct["mult_l16"]),
                    "mcnemar_add_vs_mult06": mcnemar_exact(correct["add_l4"], correct["mult_l0.6"]),
                }
        finally:
            llm.flush()
        res[judge] = out
        path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    _check_first60_a(res)
    lines = ["# N34: decision accuracy at n=120 (k=5, Wilson 95% CI)", "",
             "| judge | no retrieval | oracle | cond | add 4 | mult 0.6 | mult 16 | causal | add vs mult16 (disc, p) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for judge, r in res.items():
        c = r["controls"]
        for cond in ("clean", "leaky"):
            a = r[cond]["acc"]
            d1, d2, p = r[cond]["mcnemar_add_vs_mult16"]
            lines.append(f"| {judge} | {c['no_retrieval'][0]:.3f} | {c['oracle'][0]:.3f} | {cond} | "
                         f"{a['add_l4'][0]:.3f} | {a['mult_l0.6'][0]:.3f} | {a['mult_l16'][0]:.3f} | "
                         f"{a['causal_only'][0]:.3f} | {d1}/{d2}, p={p:.4f} |")
    (OUT_A / "RESULTS_DECISION_N34.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def _check_first60_a(res):
    """The first 60 scenarios must reproduce the published n=60 arms exactly."""
    n27 = json.loads((ROOT / "results_decision_n27" / "results_decision_n27.json").read_text(encoding="utf-8"))
    n32 = json.loads((ROOT / "results_decision_n32" / "results_decision_n32.json").read_text(encoding="utf-8"))
    for judge, r in res.items():
        ref = n27 if "/" not in judge else n32[judge]
        for cond in ("clean", "leaky"):
            for arm, v in r[cond]["correct"].items():
                assert v[:60] == ref[cond]["correct"][arm], (judge, cond, arm)


def part_b(cap: float):
    OUT_B.mkdir(exist_ok=True)
    src = ROOT / "results_decision_n33"
    for f in src.glob("*cache*.json"):
        _merge_caches(OUT_B / f.name, [f])
    D33.N, D33.OUT, D33.TCMF_BUDGET_USD = N, OUT_B, cap
    D33._client = lambda judge: _client(judge, OUT_B, cap)
    D33.main(JUDGES)
    ref = json.loads((src / "results_decision_n33.json").read_text(encoding="utf-8"))
    new = json.loads((OUT_B / "results_decision_n33.json").read_text(encoding="utf-8"))
    for judge in JUDGES:
        for k, v in new[judge]["correct"].items():
            assert v[:60] == ref[judge]["correct"][k], (judge, k)
    print("first 60 reproduce N33")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["A", "B"], required=True)
    args = ap.parse_args()
    cap = _cap()
    print(f"ledger cap for this run: ${cap:.4f}", flush=True)
    (part_a if args.part == "A" else part_b)(cap)
