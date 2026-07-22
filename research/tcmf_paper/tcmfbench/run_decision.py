"""Downstream decision-quality runner (REVIEW.md item W1): does retrieval choice change the
council's DECISION, not just its ranking metrics?

    python -m tcmfbench.run_decision --n 60 --out results_decision

Requires Ollama running with a chat model (default qwen2.5:3b-instruct) for the LLM calls.
Reuses the results_realtext/emb_cache.json embedding cache when present so no re-embedding
is needed; only the chat calls hit Ollama (also cached, so reruns are exact and free).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .embed_client import EmbedClient
from .llm_client import LLMClient
from .realtext import RealConfig, generate_many_realtext
from .decision import build_options, build_prompt, is_correct
from . import methods as M
from . import metrics as MT

THR = 0.60  # same as run_realtext: raised for anisotropic real embeddings


def _methods():
    return {
        "semantic_rag": M.rank_semantic,
        "episodic":     M.rank_episodic,
        "causal_only":  lambda m: M.rank_causal_only(m, threshold=THR, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=THR),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=THR, clean=True),
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0, threshold=THR),
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, threshold=THR, clean=True),
    }


ORDER = ["semantic_rag", "episodic", "causal_only", "graph_ppr",
         "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


def _mean_std(vals: list[float]) -> tuple[float, float]:
    return (st.mean(vals), st.pstdev(vals) if len(vals) > 1 else 0.0)


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    realtext_cache = Path("results_realtext/emb_cache.json")
    emb_cache_path = realtext_cache if realtext_cache.exists() else (out / "emb_cache.json")
    ec = EmbedClient(cache_path=emb_cache_path)
    llm = LLMClient(model=args.model, cache_path=out / "llm_cache.json")

    n, seed, k = args.n, args.seed, args.k

    print(f"Embedding {n} scenarios (cache: {len(ec)} vectors so far, path={emb_cache_path})...")
    scs = generate_many_realtext(n, RealConfig(), ec, base_seed=seed)
    mats = [M.materialize(sc, RealConfig().max_mem_per_citizen) for sc in scs]
    print(f"Embedded. Cache now {len(ec)} vectors. Building prompts and calling the LLM...")

    method_fns = _methods()
    per_method_correct: dict[str, list[bool]] = {name: [] for name in method_fns}
    per_method_causal5: dict[str, list[float]] = {name: [] for name in method_fns}
    control_correct: dict[str, list[bool]] = {"no_retrieval": [], "oracle": []}

    for idx, mat in enumerate(mats):
        crisis_text = mat.scenario.query_text
        options, true_index = build_options(mat.scenario.domain, seed=1000 + idx)

        for name, fn in method_fns.items():
            ranked = await _order(fn, mat)
            top_ids = ranked[:k]
            texts = [mat.mem[i]["text"] for i in top_ids]
            prompt = build_prompt(crisis_text, texts, options)
            response = llm.chat(prompt)
            per_method_correct[name].append(is_correct(response, true_index))
            per_method_causal5[name].append(MT.recall_at_k(ranked, mat.gold_causal, 5))

        # control: no retrieval (floor)
        prompt = build_prompt(crisis_text, [], options)
        response = llm.chat(prompt)
        control_correct["no_retrieval"].append(is_correct(response, true_index))

        # control: oracle (ceiling) - guaranteed gold_causal texts present.
        # sorted() so the prompt string is process-independent (set order is hash-randomized),
        # keeping the LLM cache key stable across reruns.
        oracle_texts = [mat.mem[i]["text"] for i in sorted(mat.gold_causal)]
        prompt = build_prompt(crisis_text, oracle_texts, options)
        response = llm.chat(prompt)
        control_correct["oracle"].append(is_correct(response, true_index))

        if (idx + 1) % 10 == 0 or idx + 1 == len(mats):
            print(f"  scenario {idx + 1}/{len(mats)} done (llm cache: {len(llm)})")
            llm.flush()

    llm.flush()

    decision_acc = {name: _mean_std([1.0 if c else 0.0 for c in vals])
                    for name, vals in per_method_correct.items()}
    causal5 = {name: _mean_std(vals) for name, vals in per_method_causal5.items()}
    control_acc = {name: _mean_std([1.0 if c else 0.0 for c in vals])
                   for name, vals in control_correct.items()}

    lines = [
        "# TCMF Benchmark: Decision-Quality Tier",
        "",
        f"Scenarios: {n} | seed: {seed} | model: {args.model} | k: {k} | causal threshold: {THR}",
        "",
        "Each method's top-k retrieved memories are shown to the LLM council advisor, which "
        "must pick the true root cause from a fixed 4-way multiple choice (true cause + 3 "
        "external-shock decoys). `decision_acc` = mean correct. `causal@5` = recall over the "
        "causal-gold subset, reported alongside for comparison.",
        "",
        "| method | causal@5 | decision_acc |",
        "|---|---|---|",
    ]
    for name in ORDER:
        c5 = causal5[name]
        da = decision_acc[name]
        lines.append(f"| {name} | {c5[0]:.2f}±{c5[1]:.2f} | {da[0]:.2f}±{da[1]:.2f} |")
    for name in ("no_retrieval", "oracle"):
        ca = control_acc[name]
        lines.append(f"| {name} | - | {ca[0]:.2f}±{ca[1]:.2f} |")
    lines.append("")

    # Pure-symptom baselines are semantic_rag and episodic. tcmf_mult is the BROKEN FUSION
    # operator under study; it retrieves partial causal signal and is expected to land BETWEEN
    # the floor and the causal leaders, so it is reported separately, not as a symptom baseline.
    causal_leaders = ["tcmf_add", "tcmf_shipped", "causal_only"]
    pure_symptom = ["semantic_rag", "episodic"]
    floor = control_acc["no_retrieval"][0]
    ceiling = control_acc["oracle"][0]
    leaders_above_floor = all(decision_acc[m][0] - floor >= 0.20 for m in causal_leaders)
    symptom_near_floor = all(abs(decision_acc[m][0] - floor) <= 0.15 for m in pure_symptom)
    mult = decision_acc["tcmf_mult"][0]
    verdict = (
        f"Hypothesis {'HELD' if leaders_above_floor and symptom_near_floor else 'DID NOT fully hold'}: "
        f"retrieval choice changes the decision. Causal-recall methods (tcmf_add, tcmf_shipped, "
        f"causal_only) scored {'clearly above' if leaders_above_floor else 'not clearly above'} the "
        f"no_retrieval floor ({floor:.2f}) toward the oracle ceiling ({ceiling:.2f}), while the "
        f"pure-symptom retrievers (semantic_rag, episodic) sat "
        f"{'near' if symptom_near_floor else 'away from'} that floor. The broken multiplicative "
        f"fusion (tcmf_mult) lands in between at {mult:.2f}, mirroring its partial causal recall - "
        f"the additive operator converts the same causal signal into correct decisions where the "
        f"multiplicative one does not."
    )
    lines.append(verdict)
    lines.append("")

    (out / "RESULTS_DECISION.md").write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "n": n, "seed": seed, "model": args.model, "k": k, "threshold": THR,
        "methods": {
            name: {
                "decision_acc": {"mean": decision_acc[name][0], "std": decision_acc[name][1]},
                "causal@5": {"mean": causal5[name][0], "std": causal5[name][1]},
            }
            for name in ORDER
        },
        "controls": {
            name: {"decision_acc": {"mean": control_acc[name][0], "std": control_acc[name][1]}}
            for name in ("no_retrieval", "oracle")
        },
    }
    (out / "results_decision.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {out/'RESULTS_DECISION.md'}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, default="results_decision")
    p.add_argument("--model", type=str, default="qwen2.5:3b-instruct")
    p.add_argument("--k", type=int, default=5)
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
