"""N33: does a graph built by an LLM change the downstream decision?

N31/N31b measured retrieval on graphs that language models built; N32 measured decisions only on
authored leaks. This joins them. The 60 decision scenarios are the first 60 of N31's 120 (same
seeds), with N31's background events and N31b's memory per background event. For each scenario we
retrieve with the true chain, the Llama-3.3-70B graph and the Gemini-2.5-Flash graph (edges read
from N31's cached ``graphs_*.json``), for additive (lambda 4) and multiplicative (lambda 16) fusion
under both depth weightings (tau 0.60), and ask the N27 decision question of three judges: the
local Qwen2.5-3B and, through the budget-capped OpenRouter client, Llama-3.3-70B and
Gemini-2.5-Flash.

    python -m tcmfbench.run_decision_n33 --judges qwen2.5:3b-instruct meta-llama/llama-3.3-70b-instruct google/gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import llm_graph as G
from .decision import build_options, build_prompt, is_correct
from .embed_client import EmbedClient
from .llm_client import LLMClient
from .openrouter_client import Ledger, OpenRouterClient
from .realtext import RealConfig
from .run_decision_n27 import K, mcnemar_exact
from .run_llmgraph_n31 import LEDGER, OUT as N31, TAU, TCMF_BUDGET_USD, scenarios
from .run_llmgraph_n31b import with_bg_memories
from .stats import wilson_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_decision_n33"
N = 60
GRAPHS = {"true chain": None, "llama-70b": "meta-llama_llama-3.3-70b-instruct",
          "gemini-flash": "google_gemini-2.5-flash"}


def _client(judge: str):
    if "/" in judge:
        return OpenRouterClient(judge, OUT / f"cache_{judge.replace('/', '_')}.json",
                                Ledger(LEDGER, TCMF_BUDGET_USD), max_tokens=200)
    return LLMClient(model=judge, host="http://127.0.0.1:11434", cache_path=OUT / "llm_cache.json",
                     timeout=300.0)


def _top(mat, fr, op):
    ids = list(mat.all_ids)
    e_d = M._episodic_scores(mat)
    b_d = M._causal_boosts(mat, TAU, clean=True, favor_root=fr)
    e = np.array([e_d[i] for i in ids])
    eh_d = M._minmax(e_d)
    eh = np.array([eh_d[i] for i in ids])
    b = np.array([b_d[i] for i in ids])
    s = eh + 4 * b if op == "add" else e * (1 + 16 * b)
    return [ids[k] for k in np.argsort(-s, kind="stable")[:K]]


def build():
    scs = scenarios()[:N]
    ec = EmbedClient(cache_path=N31 / "emb_cache.json")
    rich = [with_bg_memories(sc, i, ec)[0] for i, sc in enumerate(scs)]
    ec.flush()
    edges = {}
    for name, f in GRAPHS.items():
        if f is None:
            edges[name] = [list(s.edges) for s in scs]
        else:
            g = json.loads((N31 / f"graphs_{f}.json").read_text(encoding="utf-8"))[:N]
            assert [x["scenario"] for x in g] == [s.scenario_id for s in scs]
            edges[name] = [[tuple(e) for e in x["edges"]] for x in g]
    rcfg = RealConfig()
    tops = {}
    for name, es in edges.items():
        mats = [M.materialize(G.with_edges(s, e), rcfg.max_mem_per_citizen) for s, e in zip(rich, es)]
        for fr, tag in ((False, "prox"), (True, "root")):
            for op in ("add", "mult"):
                tops[f"{name}|{op}|{tag}"] = [[m.mem[i]["text"] for i in _top(m, fr, op)] for m in mats]
    return scs, tops


def main(judges):
    OUT.mkdir(exist_ok=True)
    scs, tops = build()
    path = OUT / "results_decision_n33.json"
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for judge in judges:
        llm = _client(judge)
        correct = {k: [] for k in tops}
        try:
            for idx, sc in enumerate(scs):
                options, true_index = build_options(sc.domain, seed=1000 + idx)
                for k in tops:
                    ans = llm.chat(build_prompt(sc.query_text, tops[k][idx], options))
                    correct[k].append(is_correct(ans, true_index))
                if (idx + 1) % 20 == 0:
                    llm.flush()
                    print(judge, idx + 1, flush=True)
        finally:
            llm.flush()
        r = {"acc": {k: list(wilson_ci(sum(v), len(v))) for k, v in correct.items()},
             "correct": {k: [bool(x) for x in v] for k, v in correct.items()}}
        r["mcnemar"] = {}
        for tag in ("prox", "root"):
            for g in ("llama-70b", "gemini-flash"):
                r["mcnemar"][f"true_vs_{g}|add|{tag}"] = mcnemar_exact(correct[f"true chain|add|{tag}"],
                                                                       correct[f"{g}|add|{tag}"])
                r["mcnemar"][f"{g}|add_vs_mult|{tag}"] = mcnemar_exact(correct[f"{g}|add|{tag}"],
                                                                       correct[f"{g}|mult|{tag}"])
        res[judge] = r
        path.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(judge, {k: round(v[0], 2) for k, v in r["acc"].items()}, flush=True)
    lines = ["# N33: decisions from LLM-built graphs (n=60, background memories, tau=0.60)", "",
             "| judge | graph | add prox | mult prox | add root | mult root |", "|---|---|---|---|---|---|"]
    for judge, r in res.items():
        for g in GRAPHS:
            a = r["acc"]
            lines.append(f"| {judge} | {g} | {a[g + '|add|prox'][0]:.2f} | {a[g + '|mult|prox'][0]:.2f} | "
                         f"{a[g + '|add|root'][0]:.2f} | {a[g + '|mult|root'][0]:.2f} |")
    (OUT / "RESULTS_DECISION_N33.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", nargs="+", required=True)
    main(ap.parse_args().judges)
