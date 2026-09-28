"""N31: a causal graph built by an LLM instead of by us.

Every other tier hands the retriever an authored graph (clean, or with leaks we placed). Here a
small local model (qwen2.5:3b-instruct, temperature 0) reads a scenario's event log, the true
chain mixed with 16 unrelated background events, and names the direct causes of each event it is
asked about. We ask the same way the retriever searches: first for the crisis, then for every
cause it names, up to the retriever's depth cap. The resulting edges replace the scenario's own,
so the model's mistakes become the only source of leakage, and we measure where they land.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .scenario import Scenario

# Chosen on a separate tuning set (20 scenarios, seeds 50000+) by best mean F1 across qwen2.5:3b and
# mistral:7b over three candidate prompts (N31); the 120 evaluation scenarios played no part.
PROMPT = """Below is a log of events in a city, in time order.

{log}

Later, this happened: "{target}"

Which of the numbered events helped cause it? First explain your reasoning in one or two
sentences. Then on the last line write CAUSES: followed by the event numbers separated by commas,
or CAUSES: NONE."""


@dataclass
class InducedGraph:
    edges: list[tuple[str, str]]
    queried: list[str]
    calls: int
    capped: bool
    unparsed: int = 0


def _order_key(sc: Scenario):
    """Strict time order. Chain events can share a tick, so ties keep the chain's own order
    (root first) and put background events after chain events at the same tick."""
    chain = {e.id: i for i, e in enumerate(e for e in sc.events if "_bg" not in e.id)}
    return {e.id: (e.tick, 0 if e.id in chain else 1, chain.get(e.id, 0), e.id) for e in sc.events}


def _earlier(sc: Scenario, target_id: str) -> list:
    key = _order_key(sc)
    t = key[target_id]
    return sorted((e for e in sc.events if key[e.id] < t), key=lambda e: key[e.id])


def parse_causes(text: str, n: int) -> list[int]:
    """1-based indices named on the model's last CAUSES: line, in range, deduplicated. An answer
    with no CAUSES: line names nothing (counted as a parse failure by the runner)."""
    m = re.findall(r"CAUSES:\s*(.*)", text)
    if not m:
        return []
    text = m[-1]
    if re.search(r"\bnone\b", text, re.I) and not re.search(r"\d", text):
        return []
    out = []
    for m in re.findall(r"\d+", text):
        k = int(m)
        if 1 <= k <= n and k not in out:
            out.append(k)
    return out


def induce(sc: Scenario, llm, max_depth: int = 4, max_calls: int = 14) -> InducedGraph:
    edges: list[tuple[str, str]] = []
    depth = {sc.crisis_event_id: 0}
    queue = [sc.crisis_event_id]
    ev = {e.id: e for e in sc.events}
    calls = 0
    queried = []
    capped = False
    unparsed = 0
    while queue:
        tid = queue.pop(0)
        if depth[tid] >= max_depth:
            continue
        cands = _earlier(sc, tid)
        if not cands:
            continue
        if calls >= max_calls:
            capped = True
            break
        log = "\n".join(f"[{k}] {e.text}" for k, e in enumerate(cands, 1))
        ans = llm.chat(PROMPT.format(log=log, target=ev[tid].text))
        calls += 1
        queried.append(tid)
        if "CAUSES:" not in ans:
            unparsed += 1
        for k in parse_causes(ans, len(cands)):
            src = cands[k - 1].id
            edges.append((src, tid))
            if src not in depth:
                depth[src] = depth[tid] + 1
                queue.append(src)
    return InducedGraph(edges=edges, queried=queried, calls=calls, capped=capped, unparsed=unparsed)


def with_edges(sc: Scenario, edges: list[tuple[str, str]]) -> Scenario:
    return replace(sc, edges=list(edges))
