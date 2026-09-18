"""N19: does BM25's benchmark failure survive removing the "(topic N)" scaffolding from
memory text?

Section~sec:more-baselines traces BM25's failure (pure recall@5 = 0.00, mixed causal@5 = 0.05)
to a specific artifact: every memory's text is generated as boilerplate embedding scaffolding
(``generator.py``'s ``f"symptom report {d} (topic {surface})"`` and siblings), and a
distractor's topic id is always identical to the crisis query's own by construction, so BM25
locks onto that shared literal token and monopolizes the top ranks with distractors.

Embeddings in this benchmark are synthesized independently of memory text (angle-mixing,
Section 4), and BM25 is the only method that reads ``mat.mem[i]["text"]``/``mat.scenario
.query_text`` at all - so stripping the scaffolding changes nothing for any other method's
score. This reruns BM25, and only BM25, on the identical TEST-split scenarios (same seeds,
same protocol) already used for Table~tab:more-baselines.

    python -m tcmfbench.run_bm25_descaffold_n19 --out results_bm25_descaffold
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
from pathlib import Path

import numpy as np

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from . import run_tuned
from .generator import GenConfig
from .mixed import MixedConfig
from .stats import bootstrap_ci

TEST_SEEDS = run_tuned.TEST_SEEDS
N = 300

# The N07 tune sweep (results_baselines_{pure,mixed}/results_baselines.json,
# "new_selected"."bm25_k1") selected k1=0.5 in both regimes - loaded here, not re-derived,
# same convention run_baselines.py itself uses for the pre-existing N03-tuned operators.
BM25_K1 = 0.5

_TOPIC_RE = re.compile(r"\s*\(topic \d+\)")


def descaffold(mat: M.Materialized) -> M.Materialized:
    """A copy of ``mat`` with the literal ``(topic N)`` suffix stripped from every memory's
    text and from the query text. Every other field - embeddings, ids, gold sets, the causal
    graph - is untouched."""
    stripped_mem = {
        i: {**rec, "text": _TOPIC_RE.sub("", rec["text"])} for i, rec in mat.mem.items()
    }
    new_scenario = dataclasses.replace(
        mat.scenario, query_text=_TOPIC_RE.sub("", mat.scenario.query_text)
    )
    return dataclasses.replace(mat, scenario=new_scenario, mem=stripped_mem)


def _score_pure(ranked, mat) -> float:
    return MT.recall_at_k(ranked, mat.gold_ids, 5)


def _score_mixed(ranked, mat) -> float:
    return MT.recall_at_k(ranked, mat.gold_causal, 5)


def _run_regime(regime: str, n: int) -> dict:
    # Realistic pool (20 distractors, 55 noise) - matches results_baselines_{pure,mixed}'s own
    # committed config exactly, since this is a direct rerun of that Table's BM25 row.
    overrides = {"n_distractors": 20, "n_noise": 55}
    cfg = GenConfig(**overrides) if regime == "pure" else MixedConfig(**overrides)
    mats = run_tuned._pool_mats(regime, cfg, n, TEST_SEEDS)
    score_fn = _score_pure if regime == "pure" else _score_mixed
    metric = "recall@5" if regime == "pure" else "causal@5"

    scaffolded = [score_fn(M.rank_bm25(m, k1=BM25_K1), m) for m in mats]
    stripped = [score_fn(M.rank_bm25(descaffold(m), k1=BM25_K1), m) for m in mats]

    # Sanity check baked into the run itself, not just the offline test: confirm the
    # stripped text really shares no token with the query for a sample of scenarios, so a
    # silent no-op stripping regex can't produce a false "no change" result.
    sample = mats[0]
    stripped_sample = descaffold(sample)
    q_terms = set(M._tokenize(stripped_sample.scenario.query_text))
    any_overlap = any(
        q_terms & set(M._tokenize(rec["text"])) for rec in stripped_sample.mem.values()
    )

    return {
        "regime": regime,
        "metric": metric,
        "n": len(mats),
        "bm25_scaffolded": bootstrap_ci(np.array(scaffolded), seed=0),
        "bm25_descaffolded": bootstrap_ci(np.array(stripped), seed=0),
        "descaffold_removes_all_topic_overlap": not any_overlap,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="N19: BM25 rerun with topic-id scaffolding stripped")
    p.add_argument("--out", default="results_bm25_descaffold")
    p.add_argument("--n", type=int, default=N)
    args = p.parse_args()

    results = {regime: _run_regime(regime, args.n) for regime in ("pure", "mixed")}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results_bm25_descaffold.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    for regime, r in results.items():
        lo_s, mean_s, hi_s = r["bm25_scaffolded"][1], r["bm25_scaffolded"][0], r["bm25_scaffolded"][2]
        lo_d, mean_d, hi_d = r["bm25_descaffolded"][1], r["bm25_descaffolded"][0], r["bm25_descaffolded"][2]
        print(
            f"{regime:6s} {r['metric']:10s} n={r['n']:4d}  "
            f"scaffolded={mean_s:.3f} [{lo_s:.3f},{hi_s:.3f}]  "
            f"descaffolded={mean_d:.3f} [{lo_d:.3f},{hi_d:.3f}]  "
            f"clean_strip={r['descaffold_removes_all_topic_overlap']}"
        )
    print(f"\nWrote {out_dir / 'results_bm25_descaffold.json'}")


if __name__ == "__main__":
    main()
