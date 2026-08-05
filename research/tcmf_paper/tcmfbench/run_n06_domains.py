"""N06: embed the N05 real-text domains and retune the causal-similarity threshold per domain
on a held-out split, following the N03 tune/test protocol.

    python -m tcmfbench.run_n06_domains --out results_n06

Requires Ollama running with nomic-embed-text (embedding) and qwen2.5:3b-instruct (decision
tier). Reuses results_realtext/emb_cache.json and results_decision/llm_cache.json as caches so
a rerun (local or a later cloud night with the caches committed) hits neither server again.

Per domain: TUNE_N scenarios select THR by mean tcmf_add recall@5 (TUNE only, never inspecting
TEST while selecting - same rule N03 uses for lambda/alpha/c). TEST_N scenarios then run the
full 8-method eval plus the decision tier at the domain's selected THR. Reported strictly per
domain, never pooled - pooling would hide a domain where the story does not replicate.
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
from .realtext import RealConfig, DOMAINS, generate_many_realtext
from .decision import build_options, build_prompt, is_correct
from . import methods as M
from . import metrics as MT

KS = (3, 5, 10)
TUNE_N = 10
TEST_N = 15
THR_GRID = [0.45, 0.55, 0.60, 0.65, 0.75]  # centered on run_realtext.py's manually-picked 0.60
SELECTION_METRIC = "recall@5"
SELECTION_METHOD = "tcmf_add"  # the paper's shipped-fix operator; same convention as run_tuned.py


def _methods(thr: float):
    return {
        "semantic_rag": M.rank_semantic,
        "episodic":     M.rank_episodic,
        "causal_only":  lambda m: M.rank_causal_only(m, threshold=thr, clean=True),
        "graph_ppr":    M.rank_graph_ppr,
        "tcmf_mult":    lambda m: M.rank_tcmf_multiplicative(m, lam=0.6, threshold=thr),
        "tcmf_add":     lambda m: M.rank_tcmf_additive(m, lam=4.0, threshold=thr, clean=True),
        "tcmf_shipped": lambda m: M.rank_tcmf(m, lam=2.0, threshold=thr),
        "tcmf_rrf":     lambda m: M.rank_tcmf_rrf(m, threshold=thr, clean=True),
    }


ORDER = ["semantic_rag", "episodic", "causal_only", "graph_ppr",
         "tcmf_mult", "tcmf_add", "tcmf_shipped", "tcmf_rrf"]
_COLS = [f"recall@{k}" for k in KS] + ["causal@5", "semantic@5", "root_mrr", "root_rank"]


def _score(ranked, mat):
    out = {f"recall@{k}": MT.recall_at_k(ranked, mat.gold_ids, k) for k in KS}
    out["causal@5"] = MT.recall_at_k(ranked, mat.gold_causal, 5)
    out["semantic@5"] = MT.recall_at_k(ranked, mat.gold_semantic, 5)
    out["root_mrr"] = MT.reciprocal_rank(ranked, mat.root_id)
    out["root_rank"] = MT.rank_of(ranked, mat.root_id) or (len(ranked) + 1)
    return out


def _agg(rows):
    return {k: (st.mean(r[k] for r in rows),
                st.pstdev([r[k] for r in rows]) if len(rows) > 1 else 0.0)
            for k in rows[0]}


async def _order(fn, mat):
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


async def _eval(mats, method_fns):
    per = {n: [] for n in method_fns}
    for mat in mats:
        for name, fn in method_fns.items():
            per[name].append(_score(await _order(fn, mat), mat))
    return {n: _agg(rows) for n, rows in per.items()}


async def _select_threshold(tune_mats) -> tuple[float, dict[float, float]]:
    scored = {}
    for thr in THR_GRID:
        fn = _methods(thr)[SELECTION_METHOD]
        rows = [_score(await _order(fn, mat), mat) for mat in tune_mats]
        scored[thr] = st.mean(r[SELECTION_METRIC] for r in rows)
    best = max(THR_GRID, key=lambda t: (scored[t], -t))  # ties -> smaller (cheaper) threshold
    return best, scored


def _table(title, results, thr):
    lines = [f"### {title} (threshold={thr})", "", "| method | " + " | ".join(_COLS) + " |",
             "|" + "---|" * (len(_COLS) + 1)]
    for n in ORDER:
        a = results[n]
        cells = [f"{a[c][0]:.2f}±{a[c][1]:.2f}" if c != "root_rank" else f"{a[c][0]:.1f}"
                 for c in _COLS]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def _decision(mats, thr, llm, domain_name):
    method_fns = _methods(thr)
    per_correct = {n: [] for n in method_fns}
    per_causal5 = {n: [] for n in method_fns}
    control = {"no_retrieval": [], "oracle": []}
    for idx, mat in enumerate(mats):
        crisis_text = mat.scenario.query_text
        options, true_index = build_options(domain_name, seed=2000 + idx)
        for name, fn in method_fns.items():
            ranked = await _order(fn, mat)
            top_ids = ranked[:5]
            texts = [mat.mem[i]["text"] for i in top_ids]
            prompt = build_prompt(crisis_text, texts, options)
            response = llm.chat(prompt)
            per_correct[name].append(is_correct(response, true_index))
            per_causal5[name].append(MT.recall_at_k(ranked, mat.gold_causal, 5))
        prompt = build_prompt(crisis_text, [], options)
        control["no_retrieval"].append(is_correct(llm.chat(prompt), true_index))
        oracle_texts = [mat.mem[i]["text"] for i in sorted(mat.gold_causal)]
        prompt = build_prompt(crisis_text, oracle_texts, options)
        control["oracle"].append(is_correct(llm.chat(prompt), true_index))
    llm.flush()
    acc = {n: st.mean(1.0 if c else 0.0 for c in v) for n, v in per_correct.items()}
    c5 = {n: st.mean(v) for n, v in per_causal5.items()}
    ctrl = {n: st.mean(1.0 if c else 0.0 for c in v) for n, v in control.items()}
    return acc, c5, ctrl


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    realtext_cache = Path("results_realtext/emb_cache.json")
    emb_cache_path = realtext_cache if realtext_cache.parent.exists() else (out / "emb_cache.json")
    ec = EmbedClient(cache_path=emb_cache_path)

    decision_cache = Path("results_decision/llm_cache.json")
    llm_cache_path = decision_cache if decision_cache.parent.exists() else (out / "llm_cache.json")
    llm = LLMClient(model=args.model, cache_path=llm_cache_path)

    cfg = RealConfig()
    per_domain = {}
    replicated_by_domain: dict[str, bool] = {}
    md_sections = ["# TCMF Benchmark: N06 - per-domain tuned real-text tier", "",
                   f"Encoder: nomic-embed-text | decision model: {args.model} | "
                   f"tune/test = {TUNE_N}/{TEST_N} per domain | threshold grid: {THR_GRID}",
                   "",
                   "Reported strictly per domain, never pooled. Threshold selected on TUNE by "
                   f"mean {SELECTION_METHOD} {SELECTION_METRIC}; TEST split never inspected "
                   "while selecting.", ""]

    for di, dom in enumerate(DOMAINS):
        name = dom["name"]
        print(f"=== domain {di+1}/{len(DOMAINS)}: {name} ===")
        base = di * 10_000
        tune_scs = generate_many_realtext(TUNE_N, cfg, ec, base_seed=base, domain_idx=di)
        test_scs = generate_many_realtext(TEST_N, cfg, ec, base_seed=base + TUNE_N, domain_idx=di)
        tune_mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in tune_scs]
        test_mats = [M.materialize(sc, cfg.max_mem_per_citizen) for sc in test_scs]
        ec.flush()

        thr, sweep = await _select_threshold(tune_mats)
        print(f"  selected threshold={thr} (sweep={sweep})")

        main = await _eval(test_mats, _methods(thr))
        acc, c5, ctrl = await _decision(test_mats, thr, llm, name)

        per_domain[name] = {
            "threshold": thr, "sweep": sweep,
            "main": {nm: {k: {"mean": v[0], "std": v[1]} for k, v in a.items()}
                     for nm, a in main.items()},
            "decision_acc": acc, "decision_causal5": c5, "decision_controls": ctrl,
        }

        md_sections.append(f"## {name}")
        md_sections.append("")
        md_sections.append(_table("Main comparison", main, thr))
        md_sections.append("")
        md_sections.append("| method | causal@5 | decision_acc |")
        md_sections.append("|---|---|---|")
        for n in ORDER:
            md_sections.append(f"| {n} | {c5[n]:.2f} | {acc[n]:.2f} |")
        for n in ("no_retrieval", "oracle"):
            md_sections.append(f"| {n} | - | {ctrl[n]:.2f} |")
        floor = ctrl["no_retrieval"]
        ceiling = ctrl["oracle"]
        leaders = ["tcmf_add", "tcmf_shipped", "causal_only"]
        symptom = ["semantic_rag", "episodic"]
        leaders_above = all(acc[m] - floor >= 0.20 for m in leaders)
        symptom_near = all(abs(acc[m] - floor) <= 0.15 for m in symptom)
        replicated = leaders_above and symptom_near and main["tcmf_add"]["recall@10"][0] > main["tcmf_mult"]["recall@10"][0]
        replicated_by_domain[name] = replicated
        md_sections.append("")
        md_sections.append(
            f"**{name}: story {'REPLICATES' if replicated else 'DOES NOT fully replicate'}.** "
            f"floor={floor:.2f} ceiling={ceiling:.2f} additive_recall@10="
            f"{main['tcmf_add']['recall@10'][0]:.2f} multiplicative_recall@10="
            f"{main['tcmf_mult']['recall@10'][0]:.2f}."
        )
        md_sections.append("")

    n_replicated = sum(1 for v in replicated_by_domain.values() if v)
    md_sections.insert(4, f"**{n_replicated}/{len(DOMAINS)} domains replicate the qualitative "
                          f"story (additive >> multiplicative; decision accuracy tracks causal "
                          f"recall), reported per-domain above - see each domain's verdict line.**")
    md_sections.insert(5, "")

    (out / "RESULTS_N06.md").write_text("\n".join(md_sections), encoding="utf-8")
    (out / "results_n06.json").write_text(json.dumps({
        "tune_n": TUNE_N, "test_n": TEST_N, "threshold_grid": THR_GRID,
        "selection_method": SELECTION_METHOD, "selection_metric": SELECTION_METRIC,
        "replicated_by_domain": replicated_by_domain,
        "domains": per_domain,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out/'RESULTS_N06.md'}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="results_n06")
    p.add_argument("--model", type=str, default="qwen2.5:3b-instruct")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
