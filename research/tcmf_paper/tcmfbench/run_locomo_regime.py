"""N18: measure the paper's retrieval regime on the public LoCoMo benchmark.

LOCAL-ONLY: needs Ollama with ``nomic-embed-text``. The embedding cache is ~200 MB for the
full dataset and is deliberately NOT committed, so a cloud agent cannot rerun this offline.
The derived per-question results in ``results_locomo/`` ARE committed, and every number in the
paper comes from that file.

The LoCoMo dataset is third-party and not vendored. Fetch it first:
    curl -L -o locomo10.json \\
      https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json

Run:
    python -m tcmfbench.run_locomo_regime --data locomo10.json --out results_locomo
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .embed_client import EmbedClient
from .locomo_regime import (DOC_PREFIX, QUERY_PREFIX, gold_units, load_locomo, rank_units,
                            score_question, units_for)
from .stats import bootstrap_ci

# 127.0.0.1, not localhost: on Windows "localhost" resolves IPv6-first and the request hangs
# to timeout even with Ollama running.
DEFAULT_HOST = "http://127.0.0.1:11434"


def run_condition(convs, client: EmbedClient, unit: str, prefix: bool) -> dict:
    qp, dp = (QUERY_PREFIX, DOC_PREFIX) if prefix else ("", "")
    per_question = []
    for conv in convs:
        if not conv.questions:
            continue
        units = units_for(conv, unit)
        vecs = [(uid, client.embed(dp + text)) for uid, text in units]
        for qi, q in enumerate(conv.questions):
            qv = client.embed(qp + q["question"])
            ranks = rank_units(qv, vecs)
            row = score_question(ranks, gold_units(q, conv, unit))
            row["sample_id"] = conv.sample_id
            # Index into this conversation's filtered multi-hop list, not the question text:
            # LoCoMo is third-party data and this results file is committed to a public repo.
            # The index is stable given the dataset, so rows stay auditable by re-running.
            row["question_index"] = qi
            per_question.append(row)
    client.flush()

    worst = [r["worst_gold_rank"] for r in per_question]
    r5 = [r["recall@5"] for r in per_question]
    r10 = [r["recall@10"] for r in per_question]
    r5_pt, r5_lo, r5_hi = bootstrap_ci(r5, seed=0)
    return {
        "unit": unit,
        "prefix": prefix,
        "n_questions": len(per_question),
        "mean_pool_size": statistics.mean(r["pool_size"] for r in per_question),
        "median_worst_gold_rank": statistics.median(worst),
        "mean_recall@5": r5_pt,
        "recall@5_ci": [r5_lo, r5_hi],
        "mean_recall@10": statistics.mean(r10),
        "frac_gold_outside_top5": sum(1 for r in per_question if r["worst_gold_rank"] > 5)
                                  / len(per_question),
        "per_question": per_question,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="path to locomo10.json")
    ap.add_argument("--out", default="results_locomo")
    ap.add_argument("--cache", default=None,
                    help="embedding cache path (default: <out>/emb_cache_locomo.json, "
                         "large and gitignored)")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--model", default="nomic-embed-text")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = args.cache or str(out / "emb_cache_locomo.json")
    client = EmbedClient(model=args.model, host=args.host, cache_path=cache)

    convs = load_locomo(args.data)
    n_q = sum(len(c.questions) for c in convs)
    print(f"{len(convs)} conversations, {n_q} multi-hop questions with resolvable evidence")

    conditions = []
    for unit in ("turn", "session"):
        for prefix in (False, True):
            print(f"  running unit={unit} prefix={prefix} ...", flush=True)
            conditions.append(run_condition(convs, client, unit, prefix))

    payload = {"dataset": "LoCoMo (locomo10.json)", "model": args.model,
               "conditions": conditions}
    (out / "results_locomo.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Does the TCMF regime occur in LoCoMo?",
        "",
        f"{len(convs)} conversations, {conditions[0]['n_questions']} multi-hop questions "
        f"(category 1, >= 2 annotated evidence spans). Encoder: `{args.model}`.",
        "",
        "Rank every unit of the conversation by cosine similarity to the question, then see "
        "where the annotated gold evidence lands.",
        "",
        "| unit | nomic prefix | pool | median worst-gold rank | recall@5 [95% CI] | "
        "recall@10 | gold outside top-5 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in conditions:
        lo, hi = c["recall@5_ci"]
        lines.append(
            f"| {c['unit']} | {'yes' if c['prefix'] else 'no'} | {c['mean_pool_size']:.0f} | "
            f"{c['median_worst_gold_rank']:.0f} | {c['mean_recall@5']:.3f} "
            f"[{lo:.3f}, {hi:.3f}] | {c['mean_recall@10']:.3f} | "
            f"{c['frac_gold_outside_top5']:.1%} |")
    sess = next(c for c in conditions if c["unit"] == "session" and not c["prefix"])
    lines += [
        "",
        "**Report the session rows.** Retrieving single dialogue turns makes semantic search "
        "look far worse than it is; sessions are the granularity real systems use.",
        "",
        f"- At session granularity, assembling the full evidence set takes a median of "
        f"{sess['median_worst_gold_rank']:.0f} of {sess['mean_pool_size']:.0f} sessions.",
        f"- recall@5 is {sess['mean_recall@5']:.3f}, and "
        f"{sess['frac_gold_outside_top5']:.1%} of questions have a needed session outside "
        f"the top 5.",
        "- This shows semantic similarity is INSUFFICIENT. It does not show that causal "
        "structure is the remedy; LoCoMo ships no causal graph. See `locomo_regime.py`.",
    ]
    (out / "RESULTS_LOCOMO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
