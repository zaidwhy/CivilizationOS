"""Tier B: does the memory architecture change the decision a reader makes?

    python -m tcmfaudit.run_decision                                   # qwen2.5:3b + nomic
    python -m tcmfaudit.run_decision --reader llama3.2:3b              # second reader
    python -m tcmfaudit.run_decision --encoder all-minilm              # second encoder

Needs a local Ollama. Every model call is cached in ``results/decision/cache_*.jsonl`` with
its raw output, so a rerun is offline and a killed run resumes. Rows land in
``results/decision/rows_<reader>__<encoder>.jsonl``.
"""
from __future__ import annotations

import argparse
import json
import re
import time

import numpy as np

from . import AUDIT_ROOT, graphs
from . import retrievers as R
from .ollama import Generator, embed_all
from .textworld import TextWorld, all_texts, build, scenario_specs, wrong_root

RESULTS = AUDIT_ROOT / "results" / "decision"
BUDGET = 5                    # memories every retrieval arm may show the reader
SUMMARY_CHUNK = 16
SUMMARY_WORDS = 100
SUMMARY_MODEL = "qwen2.5:3b-instruct"
PAPER_THRESHOLD = 0.60        # the paper's retuned similarity threshold for nomic-embed-text
LETTERS = "ABCD"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def records_block(tw: TextWorld, indices: list[int]) -> str:
    return "RECORDS:\n" + "\n".join(f"- {tw.mem_text[i]}" for i in indices)


def chain_block(ev_text: list[str], ticks: np.ndarray, og: graphs.ObservedGraph) -> str:
    events = sorted(graphs.ancestors(og), key=lambda e: int(ticks[e]))
    return "CAUSAL CHAIN (from the event log):\n" + "\n".join(f"- {ev_text[e]}" for e in events)


def production_block(tw: TextWorld, og: graphs.ObservedGraph, memories: int) -> tuple[str, list[int]]:
    """The prompt block production builds for the council (``TCMFContext.context_text`` minus
    its CRISIS line, which the question already carries), cut to ``memories`` evidence lines."""
    ctx, index_of = R.run_tcmf_deployed(tw.world, og, k=12, mem_text=tw.mem_text, ev_text=tw.ev_text)
    _, evidence, chain = ctx.context_text.split("\n\n")
    header, *lines = evidence.split("\n")
    shown = [index_of[mem.id] for _, mem, _ in ctx.fused_memories[:memories]]
    return "\n".join([header, *lines[:memories]]) + "\n\n" + chain, shown


def rolling_summary(tw: TextWorld, summarize: Generator) -> str:
    """Summary-buffer memory: records are folded into a running summary in arrival order."""
    order = np.argsort(tw.world.mem_tick, kind="stable")
    summary = "(nothing yet)"
    for start in range(0, len(order), SUMMARY_CHUNK):
        chunk = "\n".join(f"- {tw.mem_text[int(i)]}" for i in order[start:start + SUMMARY_CHUNK])
        reply = summarize(
            "You keep a running summary of a town's records.\n\n"
            f"Summary so far:\n{summary}\n\nNew records:\n{chunk}\n\n"
            f"Write the updated summary as one paragraph of at most {SUMMARY_WORDS} words. "
            "Do not list the records one by one."
        )["response"]
        summary = " ".join(reply.split()[:SUMMARY_WORDS])
    return "SUMMARY OF RECORDS:\n" + summary


def contexts(tw: TextWorld, summarize: Generator,
             embed: dict[str, np.ndarray]) -> dict[str, tuple[str, list[int]]]:
    """Arm name -> (context text, memory indices shown, empty when the arm shows none)."""
    w = tw.world
    oracle, dep = graphs.oracle(w), graphs.deployed(w)
    wrong_w, wrong_text, wrong = wrong_root(tw, np.random.default_rng([ord(c) for c in tw.scenario_id]), embed)

    def top(ranking: list[int]) -> tuple[str, list[int]]:
        return records_block(tw, ranking[:BUDGET]), ranking[:BUDGET]

    def paper_tcmf(world, og: graphs.ObservedGraph) -> list[int]:
        return R.rank_tcmf_variant(world, og, weak=False, threshold=PAPER_THRESHOLD)

    gold = sorted(w.causal_gold, key=lambda i: int(w.mem_tick[i]))
    return {
        "none": ("(no records available)", []),
        "chronological": top(R.rank_chronological(w, oracle)),
        "summary": (rolling_summary(tw, summarize), []),
        "vector": top(R.rank_vector(w, oracle)),
        "episodic": top(R.rank_episodic(w, oracle)),
        "two_hop": top(R.rank_two_hop(w, oracle)),
        "event_log_union": top(R.rank_event_log_union(w, oracle)),
        "graph_union@oracle": top(R.rank_graph_union(w, oracle)),
        "chain_text@oracle": (chain_block(tw.ev_text, w.ev_tick, oracle), []),
        "tcmf_shipped@oracle": top(R.rank_tcmf_deployed(w, oracle)),
        "tcmf_paper@oracle": top(paper_tcmf(w, oracle)),
        "tcmf_production_block@oracle": production_block(tw, oracle, 8),
        "tcmf_production_block_5@oracle": production_block(tw, oracle, BUDGET),
        "tcmf_shipped@deployed_graph": top(R.rank_tcmf_deployed(w, dep)),
        "tcmf_paper@deployed_graph": top(paper_tcmf(w, dep)),
        "tcmf_production_block@deployed_graph": production_block(tw, dep, 8),
        "tcmf_paper@wrong_graph": top(paper_tcmf(wrong_w, wrong)),
        "chain_text@wrong_graph": (chain_block(wrong_text, w.ev_tick, wrong), []),
        "gold": (records_block(tw, gold), gold),
    }


def question(tw: TextWorld, context: str) -> str:
    options = "\n".join(f"{LETTERS[i]}. {opt}" for i, opt in enumerate(tw.options))
    return (
        "You advise a town council during a crisis.\n\n"
        f"CRISIS: {tw.crisis_text}\n\n{context}\n\n"
        "Question: which earlier council decision is the root cause of this crisis?\n"
        f"{options}\n\nAnswer with one letter (A, B, C or D)."
    )


def parse_letter(response: str) -> int | None:
    # A reader that answers in a sentence names the letter after "answer is".
    match = (re.search(r"answer is[:\s]*\(?([ABCD])\b", response)
             or re.search(r"\b([ABCD])\b", response.strip()))
    return LETTERS.index(match.group(1)) if match else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reader", default="qwen2.5:3b-instruct")
    parser.add_argument("--encoder", default="nomic-embed-text")
    parser.add_argument("--limit", type=int, default=None, help="first N scenarios only (smoke run)")
    parser.add_argument("--reader-tokens", type=int, default=4,
                        help="output cap; a reader that answers in a sentence needs about 12")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    embed = embed_all(all_texts(), args.encoder, RESULTS / f"emb_{slug(args.encoder)}.json")
    reader = Generator(args.reader, RESULTS / f"cache_reader_{slug(args.reader)}.jsonl", max_tokens=args.reader_tokens)
    summarize = Generator(SUMMARY_MODEL, RESULTS / f"cache_summary_{slug(SUMMARY_MODEL)}.jsonl", max_tokens=180)

    specs = scenario_specs()[: args.limit]
    out = RESULTS / f"rows_{slug(args.reader)}__{slug(args.encoder)}.jsonl"
    started = time.perf_counter()
    rows = []
    for n_done, spec in enumerate(specs, 1):
        for link in (False, True):
            tw = build(spec, link, embed)
            root = tw.world.root_gold
            for arm, (context, shown) in contexts(tw, summarize, embed).items():
                reply = reader(question(tw, context))
                predicted = parse_letter(reply["response"])
                rows.append({
                    "scenario": tw.scenario_id, "cluster": tw.cluster, "domain": tw.domain,
                    "link": link, "arm": arm, "reader": args.reader, "encoder": args.encoder,
                    "answer": tw.answer, "predicted": predicted,
                    "correct": int(predicted == tw.answer), "unparsed": int(predicted is None),
                    "raw": reply["response"], "prompt_tokens": reply["prompt_tokens"],
                    "root_shown": int(bool(root & set(shown))),
                    "gold_shown": len(tw.world.causal_gold & set(shown)),
                    "context": context,
                })
        if n_done % 8 == 0:
            print(f"{n_done}/{len(specs)} scenarios, {reader.calls} new reader calls, "
                  f"{summarize.calls} new summary calls, {time.perf_counter() - started:.0f}s", flush=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
