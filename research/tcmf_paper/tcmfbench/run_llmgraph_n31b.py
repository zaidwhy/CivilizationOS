"""N31b: the LLM-built graphs again, with memories of the background events in the pool.

N31's background events had no memories of their own, so a false edge to one of them had nothing
to leak its boost onto; the similarity gate filtered it out. A real agent remembers more than one
story. Here every background event gets one memory, written the way the benchmark writes memories
for real events: another domain's logged decision gets that domain's first-person witness account,
another domain's crisis gets one of its symptom reports, and an ordinary city event gets its own
text. None of them is gold. The graphs are the ones N31 already built (read from
``graphs_*.json``), so this makes no LLM calls; only the new memory texts are embedded.

    python -m tcmfbench.run_llmgraph_n31b
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import llm_graph as G
from .embed_client import EmbedClient
from .realtext import DOMAINS, _NOISE, RealConfig, _fill
from .run_llmgraph_n31 import OUT, TAU, _eval, _summ, scenarios
from .scenario import MemorySpec


def _memory_for(text: str, own: str, rng):
    """(memory text, importance range) for a background event, or None if unrecognized."""
    def pref(t):
        return t.split("{")[0][:40]
    for d in DOMAINS:
        if d["name"] == own:
            continue
        for a in d["ancestors"]:
            if text.startswith(pref(a["event"])):
                return _fill(a["witness"], rng), (4.0, 7.0)
        if any(text.startswith(pref(c)) for c in d["crisis"]):
            return _fill(d["distractor"][int(rng.integers(len(d["distractor"])))], rng), (7.0, 9.0)
    if text in _NOISE:
        return text, (2.0, 5.0)
    return None


def with_bg_memories(sc, i: int, ec: EmbedClient):
    rng = np.random.default_rng([i, 31])
    mems = list(sc.memories)
    added = 0
    for e in sc.events:
        if "_bg" not in e.id:
            continue
        got = _memory_for(e.text, sc.domain or "", rng)
        if got is None:
            continue
        txt, (lo, hi) = got
        mems.append(MemorySpec(id="", citizen_id="", text=txt, tick=int(rng.integers(1, 80)), topic=-5,
                               importance=float(round(rng.uniform(lo, hi), 1)), embedding=ec.embed(txt),
                               label="noise"))
        added += 1
    return replace(sc, memories=mems), added


def main():
    scs = scenarios()
    ec = EmbedClient(cache_path=OUT / "emb_cache.json")
    rich, added = [], []
    for i, sc in enumerate(scs):
        s2, n = with_bg_memories(sc, i, ec)
        rich.append(s2)
        added.append(n)
    ec.flush()
    graphs = {"true chain": [list(s.edges) for s in scs]}
    for f in sorted(OUT.glob("graphs_*.json")):
        name = f.stem[len("graphs_"):]
        g = json.loads(f.read_text(encoding="utf-8"))
        assert [x["scenario"] for x in g] == [s.scenario_id for s in scs], f
        graphs[name] = [[tuple(e) for e in x["edges"]] for x in g]
    rcfg = RealConfig()
    res = {"tau": TAU, "n": len(scs), "memories_added_mean": float(np.mean(added)), "graphs": {}}
    for name, edges in graphs.items():
        mats = [M.materialize(G.with_edges(s, e), rcfg.max_mem_per_citizen) for s, e in zip(rich, edges)]
        for fr, tag in ((False, "prox"), (True, "root")):
            ev = [_eval(m, fr) for m in mats]
            res["graphs"][f"{name}|{tag}"] = _summ([r for r, _ in ev], [p for _, ps in ev for p in ps])
        print(name, "done", flush=True)
    (OUT / "results_llmgraph_n31b.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = [f"# N31b: LLM-built graphs with a memory for every background event (n=120, tau={TAU}, "
             f"{res['memories_added_mean']:.1f} memories added per scenario)", "",
             "| graph | weights | add l=4 | mult l=16 | add - mult16 [95% CI] | causal alone | leaked pairs | rho<1 | only-mult-fails | only-add-fails |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["graphs"].items():
        name, tag = k.split("|")
        ci = v["add_l4_minus_mult_l16_ci"]
        pp = v["pairs"]
        pr = (f"{pp['n']} | {pp['frac_rho_lt_1']:.2f} | {pp['mult_only_wrong']:.2f} | {pp['add_only_wrong']:.2f}"
              if pp["n"] else "0 | - | - | -")
        lines.append(f"| {name} | {tag} | {v['add_l4']:.3f} | {v['mult_l16']:.3f} | {ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}] | "
                     f"{v['causal']:.3f} | {pr} |")
    (OUT / "RESULTS_LLMGRAPH_N31B.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
