"""N31: which regime does a graph built by an LLM fall into?

Real text, six domains, 120 scenarios (the N26/N29 set), each event log = the true chain plus 16
background events (other domains' decisions and crises, ordinary city events). The model sees
only event texts in time order and is asked, from the crisis backward, which earlier events
caused each one (``llm_graph.induce``). Two local models: qwen2.5:3b-instruct and mistral:7b.

For each model: how many of its edges are right, how many false ancestors it adds and of what
kind, where its leaked pairs land in the (rho, beta) plane, and recall@5 for both fusions on its
graph versus on the true graph and on no graph at all (same memories, tau = 0.60).

    python -m tcmfbench.run_llmgraph_n31
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from . import llm_graph as G
from .clutter import ClutterConfig, add_clutter_realtext
from .embed_client import EmbedClient
from .llm_client import LLMClient
from .realtext import DOMAINS, _NOISE, RealConfig, generate_many_realtext
from .stats import bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_llmgraph_n31"
MODELS = ["qwen2.5:3b-instruct", "mistral:7b"]
GRID = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
TAU = 0.60
HOST = "http://127.0.0.1:11434"


class _Retry:
    """One retry on a timed-out call: a long reasoning answer on a busy local server can exceed
    the timeout once without the server being down."""

    def __init__(self, llm):
        self.llm = llm

    def chat(self, prompt):
        try:
            return self.llm.chat(prompt)
        except RuntimeError:
            return self.llm.chat(prompt)

    def flush(self):
        self.llm.flush()


def scenarios():
    cache = OUT / "emb_cache.json"
    if not cache.exists():  # seeded from N29's cache; never writes to another run's file
        shutil.copyfile(ROOT / "results_clutter_n29" / "emb_cache.json", cache)
    ec = EmbedClient(cache_path=cache)
    base = generate_many_realtext(120, RealConfig(n_domains=6), ec, base_seed=0)
    bg = ClutterConfig(n_background=16, n_false_edges=0, background_edge_prob=0.0)
    return [add_clutter_realtext(sc, bg, i, ec) for i, sc in enumerate(base)]


def _kind(text: str) -> str:
    """What a background event is: another domain's logged decision, another domain's crisis, or
    ordinary city life. Texts are filled templates, so match on the template's fixed prefix."""
    def pref(t):
        return t.split("{")[0][:40]
    for d in DOMAINS:
        if any(text.startswith(pref(c)) for c in d["crisis"]):
            return "crisis"
        if any(text.startswith(pref(a["event"])) for a in d["ancestors"]):
            return "decision"
    return "city" if text in _NOISE else "other"


def _rank(ids, score, tie=None):
    order = np.lexsort((tie, score))[::-1] if tie is not None else np.argsort(-score, kind="stable")
    return [ids[k] for k in order]


def _eval(mat, fr):
    ids = list(mat.all_ids)
    e_d = M._episodic_scores(mat)
    b_d = M._causal_boosts(mat, TAU, clean=True, favor_root=fr)
    e = np.array([e_d[i] for i in ids])
    eh_d = M._minmax(e_d)
    eh = np.array([eh_d[i] for i in ids])
    b = np.array([b_d[i] for i in ids])

    def r5(rk):
        return MT.recall_at_k(rk, mat.gold_ids, 5)

    row = {"add_l4": r5(_rank(ids, eh + 4 * b)), "mult_l16": r5(_rank(ids, e * (1 + 16 * b))),
           "causal": r5(_rank(ids, b)),
           "causal@5_add_l4": MT.recall_at_k(_rank(ids, eh + 4 * b), mat.gold_causal, 5),
           "causal@5_mult_l16": MT.recall_at_k(_rank(ids, e * (1 + 16 * b)), mat.gold_causal, 5)}
    grid = [r5(_rank(ids, e * (1 + l * b))) for l in GRID] + [r5(_rank(ids, eh * (1 + l * b))) for l in GRID]
    row["mult_grid"] = grid + [r5(_rank(ids, e * b, tie=e)), r5(_rank(ids, eh * b, tie=eh))]
    pairs = []
    for gi in mat.gold_causal:
        a = ids.index(gi)
        if b[a] <= 0:
            continue
        for j in range(len(ids)):
            if ids[j] not in mat.gold_ids and b[j] > 0:
                pairs.append((float(e[a] / e[j]), float(b[j] / b[a])))
    return row, pairs


def _summ(rows, pairs):
    d = [r["add_l4"] - r["mult_l16"] for r in rows]
    grid = np.mean([r["mult_grid"] for r in rows], axis=0)
    out = {k: float(np.mean([r[k] for r in rows]))
           for k in ("add_l4", "mult_l16", "causal", "causal@5_add_l4", "causal@5_mult_l16")}
    out["best_mult_exploratory"] = float(grid.max())
    out["add_l4_minus_mult_l16_ci"] = list(bootstrap_ci(d))
    out["wins_losses_ties_add_vs_mult16"] = [int(sum(x > 0 for x in d)), int(sum(x < 0 for x in d)),
                                             int(sum(x == 0 for x in d))]
    if pairs:
        p = np.array(pairs)
        rho, beta = p[:, 0], p[:, 1]
        out["pairs"] = {"n": len(p), "frac_rho_lt_1": float(np.mean(rho < 1)),
                        "mult_only_wrong": float(np.mean((beta < 1) & (rho <= beta))),
                        "add_only_wrong": float(np.mean((beta > 1) & (rho > beta))),
                        "both_wrong": float(np.mean((beta >= 1) & (rho <= beta))),
                        "both_right": float(np.mean((beta < 1) & (rho > beta)))}
    else:
        out["pairs"] = {"n": 0}
    return out


TCMF_BUDGET_USD = 1.50  # Zaid's allocation for all paid TCMF calls (2026-09-28); shared ledger
LEDGER = ROOT / "results_openrouter" / "ledger.json"


def make_client(model: str):
    """Local Ollama for plain names, budget-capped OpenRouter for "vendor/model" ids."""
    if "/" in model:
        from .openrouter_client import Ledger, OpenRouterClient
        return OpenRouterClient(model, OUT / f"or_cache_{model.replace('/', '_')}.json",
                                Ledger(LEDGER, TCMF_BUDGET_USD), max_tokens=1500)
    return _Retry(LLMClient(model=model, host=HOST, cache_path=OUT / "llm_cache.json", timeout=300.0,
                            num_predict=1500))  # above every cached answer; same cap as OpenRouter


def main(models=None):
    models = models or MODELS
    OUT.mkdir(exist_ok=True)
    scs = scenarios()
    prev = OUT / "results_llmgraph_n31.json"
    res = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else {}
    res.update({"tau": TAU, "n": len(scs)})
    res.setdefault("models", {})
    rcfg = RealConfig()
    # reference graphs, shared by both models
    refs = {}
    for name, edge_fn in (("true", lambda sc: sc.edges), ("none", lambda sc: [])):
        mats = [M.materialize(G.with_edges(sc, edge_fn(sc)), rcfg.max_mem_per_citizen) for sc in scs]
        for fr, tag in ((False, "prox"), (True, "root")):
            ev = [_eval(m, fr) for m in mats]
            refs[f"{name}_{tag}"] = _summ([r for r, _ in ev], [p for _, ps in ev for p in ps])
    res["reference"] = refs
    for model in models:
        llm = make_client(model)
        t0 = time.time()
        graphs = []
        for i, sc in enumerate(scs):
            graphs.append(G.induce(sc, llm))
            if i % 10 == 9:
                llm.flush()
                print(f"{model} {i + 1}/120 {time.time() - t0:.0f}s", flush=True)
        llm.flush()
        prec, rec, false_n, kinds, root_found, edge_kinds = [], [], [], {}, 0, {"chain": 0, "shortcut": 0, "reversed_or_bad": 0, "false": 0}
        mats = []
        for sc, ig in zip(scs, graphs):
            chain = [e.id for e in sc.events if "_bg" not in e.id]
            pos = {c: k for k, c in enumerate(chain)}
            for a, b in ig.edges:
                if "_bg" in a or "_bg" in b:  # any edge touching the background is false
                    edge_kinds["false"] += 1
                elif pos[b] - pos[a] == 1:
                    edge_kinds["chain"] += 1
                elif pos[b] - pos[a] > 1:
                    edge_kinds["shortcut"] += 1
                else:
                    edge_kinds["reversed_or_bad"] += 1
            mat = M.materialize(G.with_edges(sc, ig.edges), rcfg.max_mem_per_citizen)
            mats.append(mat)
            anc = set(M._ancestor_map(mat, clean=True))
            true_anc = set(chain[:-1])
            tp = len(anc & true_anc)
            prec.append(tp / len(anc) if anc else float("nan"))
            rec.append(tp / len(true_anc))
            false_n.append(len(anc - true_anc))
            root_found += chain[0] in anc
            ev = {e.id: e for e in sc.events}
            for x in anc - true_anc:
                k = _kind(ev[x].text)
                kinds[k] = kinds.get(k, 0) + 1
        m = {"calls": int(sum(g.calls for g in graphs)), "unparsed": int(sum(g.unparsed for g in graphs)),
             "capped": int(sum(g.capped for g in graphs)), "edges": edge_kinds,
             "ancestor_precision": float(np.nanmean(prec)), "ancestor_recall": float(np.mean(rec)),
             "frac_empty_graph": float(np.mean([np.isnan(p) for p in prec])),
             "false_ancestors_mean": float(np.mean(false_n)), "false_ancestor_kinds": kinds,
             "root_in_ancestors": root_found / len(scs), "seconds": time.time() - t0}
        for fr, tag in ((False, "prox"), (True, "root")):
            ev = [_eval(mt, fr) for mt in mats]
            m[f"retrieval_{tag}"] = _summ([r for r, _ in ev], [p for _, ps in ev for p in ps])
        res["models"][model] = m
        (OUT / f"graphs_{model.replace(':', '_').replace('/', '_')}.json").write_text(
            json.dumps([{"scenario": sc.scenario_id, "edges": g.edges, "calls": g.calls} for sc, g in zip(scs, graphs)]),
            encoding="utf-8")
        # one file per model, so runs of different models can proceed in parallel without
        # overwriting each other; the combined file is rebuilt from all of them
        safe = model.replace(":", "_").replace("/", "_")
        (OUT / f"model_{safe}.json").write_text(json.dumps({model: m}, indent=1), encoding="utf-8")
        for f in sorted(OUT.glob("model_*.json")):
            res["models"].update(json.loads(f.read_text(encoding="utf-8")))
        (OUT / "results_llmgraph_n31.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(model, json.dumps({k: v for k, v in m.items() if not k.startswith("retrieval")}), flush=True)
    lines = ["# N31: causal graphs built by an LLM (real text, 6 domains, n=120, tau=0.60)", "",
             "| graph | weights | add l=4 | mult l=16 | add - mult16 [95% CI] | causal alone | best mult (exploratory) | leaked pairs | rho<1 | only-mult-fails | only-add-fails |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(name, tag, v):
        ci = v["add_l4_minus_mult_l16_ci"]
        pp = v["pairs"]
        pr = (f"{pp['n']} | {pp['frac_rho_lt_1']:.2f} | {pp['mult_only_wrong']:.2f} | {pp['add_only_wrong']:.2f}"
              if pp["n"] else "0 | - | - | -")
        return (f"| {name} | {tag} | {v['add_l4']:.3f} | {v['mult_l16']:.3f} | {ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}] | "
                f"{v['causal']:.3f} | {v['best_mult_exploratory']:.3f} | {pr} |")
    for tag in ("prox", "root"):
        lines.append(row("true chain", tag, res["reference"][f"true_{tag}"]))
        lines.append(row("no graph", tag, res["reference"][f"none_{tag}"]))
        for model, m in res["models"].items():
            lines.append(row(model, tag, m[f"retrieval_{tag}"]))
    lines += ["", "## Graph quality", "", "| model | calls | unparsed | ancestor precision | ancestor recall | root found | false ancestors / scenario | false-ancestor kinds | edges (chain/shortcut/reversed/false) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for model, m in res["models"].items():
        e = m["edges"]
        lines.append(f"| {model} | {m['calls']} | {m['unparsed']} | {m['ancestor_precision']:.2f} | {m['ancestor_recall']:.2f} | "
                     f"{m['root_in_ancestors']:.2f} | {m['false_ancestors_mean']:.2f} | {m['false_ancestor_kinds']} | "
                     f"{e['chain']}/{e['shortcut']}/{e['reversed_or_bad']}/{e['false']} |")
    (OUT / "RESULTS_LLMGRAPH_N31.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=None, help="default: the two local models")
    main(ap.parse_args().models)
