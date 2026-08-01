"""Does the regime this paper is about occur in a public benchmark? (N18)

TCMF's premise is a retrieval regime, not just a method: some memory needed to answer the
current question is semantically DISSIMILAR to it while irrelevant material is similar, so
ranking by semantic similarity buries the thing you need. Every result elsewhere in this
benchmark is measured on scenarios we authored, which makes "is this regime real, or did you
construct it?" the sharpest objection available to a reviewer.

This module answers it on LoCoMo \\citep{maharana2024locomo}, a public, human-verified
long-term-conversation benchmark: take its multi-hop questions, rank every unit of the
conversation by similarity to the question, and see where the annotated gold evidence lands.

What this DOES show: semantic similarity alone does not surface the full evidence set.
What this does NOT show: that causal-ancestor reachability is the fix. LoCoMo ships no causal
graph (its generation-time event graph is not in the release; ``event_summary`` is free text
with no ids and no edges), and its multi-hop links are plausibly entity/co-reference chains
rather than causal ones. Running TCMF itself here would require inducing a causal graph, which
is out of scope and upstream of TCMF. Do not overstate this result.

Two confounds are first-class here because the first version of this measurement was wrong
about one of them:
  * granularity - retrieving single short dialogue turns makes semantic search look far worse
    than it is. Real systems retrieve sessions. Report the session number.
  * nomic prefixes - ``nomic-embed-text`` is trained with "search_query:"/"search_document:".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

QUERY_PREFIX = "search_query: "
DOC_PREFIX = "search_document: "
MULTI_HOP_CATEGORY = 1


@dataclass
class Conversation:
    """One LoCoMo conversation reduced to what this measurement needs."""
    sample_id: str
    turns: list[tuple[str, str]]                 # (dia_id, text), conversation order
    turn_to_session: dict[str, str]              # dia_id -> session key
    sessions: list[tuple[str, str]]              # (session key, concatenated text)
    questions: list[dict] = field(default_factory=list)   # multi-hop, resolvable evidence


def load_locomo(path: str | Path) -> list[Conversation]:
    """Parse the released ``locomo10.json``.

    The dataset is third-party and NOT vendored into this repo. Fetch it from
    https://github.com/snap-research/locomo (``data/locomo10.json``) and pass ``--data``.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[Conversation] = []
    for d in raw:
        conv = d["conversation"]
        session_keys = [k for k in conv
                        if k.startswith("session_") and not k.endswith("date_time")]
        turns: list[tuple[str, str]] = []
        turn_to_session: dict[str, str] = {}
        sessions: list[tuple[str, str]] = []
        for k in session_keys:
            block = [t for t in conv[k] if t.get("dia_id") and t.get("text")]
            if not block:
                continue
            for t in block:
                turns.append((t["dia_id"], t["text"]))
                turn_to_session[t["dia_id"]] = k
            sessions.append((k, "\n".join(f'{t["speaker"]}: {t["text"]}' for t in block)))

        known = set(turn_to_session)
        questions = [
            q for q in d.get("qa", [])
            if q.get("category") == MULTI_HOP_CATEGORY
            and len(q.get("evidence") or []) >= 2
            and all(e in known for e in q["evidence"])
        ]
        out.append(Conversation(str(d.get("sample_id", len(out))), turns, turn_to_session,
                                sessions, questions))
    return out


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def rank_units(query_vec, unit_vecs: list[tuple[str, list[float]]]) -> dict[str, int]:
    """1-based rank of every unit id by descending cosine similarity to the query."""
    scored = sorted(unit_vecs, key=lambda kv: cosine(query_vec, kv[1]), reverse=True)
    return {uid: i + 1 for i, (uid, _) in enumerate(scored)}


def score_question(ranks: dict[str, int], gold: set[str], ks=(5, 10)) -> dict:
    """Where the gold evidence landed, and what a top-k semantic retriever would have got.

    ``worst_gold_rank`` is the headline: to have every piece of evidence in hand you must
    retrieve at least that many units, so it is the honest cost of relying on similarity.
    """
    gold_ranks = sorted(ranks[g] for g in gold)
    out = {
        "n_gold": len(gold),
        "best_gold_rank": gold_ranks[0],
        "worst_gold_rank": gold_ranks[-1],
        "pool_size": len(ranks),
    }
    for k in ks:
        out[f"recall@{k}"] = sum(1 for r in gold_ranks if r <= k) / len(gold_ranks)
    return out


def gold_units(question: dict, conv: Conversation, unit: str) -> set[str]:
    if unit == "turn":
        return set(question["evidence"])
    if unit == "session":
        return {conv.turn_to_session[e] for e in question["evidence"]}
    raise ValueError(f"unknown unit: {unit!r}")


def units_for(conv: Conversation, unit: str) -> list[tuple[str, str]]:
    if unit == "turn":
        return conv.turns
    if unit == "session":
        return conv.sessions
    raise ValueError(f"unknown unit: {unit!r}")
