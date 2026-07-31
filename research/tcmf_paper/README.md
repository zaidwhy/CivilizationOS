# TCMF Benchmark

Controlled, fully-offline evaluation of Temporal-Causal Memory Fusion (TCMF) - the
retrieval mechanism in `api/memory/tcmf.py`. Built to answer the go/no-go question for a
paper: does causal-ancestor re-ranking of agent memory measurably beat semantic and
graph-RAG baselines, and does the shipped implementation actually exploit that signal?

The mechanism under test is the **real** `TCMFRetriever`. This package supplies a synthetic,
deterministic scenario generator with known causal ground truth, a set of retrieval baselines,
fusion-operator variants, and ranking metrics. No LLM or network access is required.

## Layout

```
tcmfbench/
  generator.py    synthetic scenarios; controlled embedding space (angle-mixed topics)
  mixed.py        mixed-regime scenarios: causal-gold + semantic-gold + edge dropout
  realtext.py     natural-language scenarios across 6 crisis domains (real-text tier)
  embed_client.py disk-cached Ollama nomic-embed-text client
  scenario.py     scenario / memory / event data model + ground-truth labels (2 gold types)
  methods.py      baselines (random, recency, semantic RAG, episodic, causal-only, graph PPR)
                  + real TCMF retriever + additive / RRF / multiplicative operator variants
  metrics.py      recall@k, root-cause MRR/rank, nDCG@k
  stats.py        bootstrap CIs + paired Wilcoxon signed-rank + Holm-Bonferroni (pure numpy)
  run_eval.py     pure regime: main comparison + ablations -> results_main/
  run_mixed.py    mixed regime: fusion beats single signals + dropout -> results_mixed/
  run_realtext.py real-text tier (needs Ollama) -> results_realtext/
  run_tuned.py    held-out tune/test split (N03) -> results_main_tuned/, results_mixed_tuned/
  run_spurious.py spurious false-ancestor edge robustness (N04) -> results_spurious/
PAPER_PLAN.md     the correct framing, related work, and phase plan
FINDINGS.md       what the runs show (read this first): F1-F7 + code fixes + real-text tier
```

## Reproduce

From the repo root, using the project venv (Python 3.14):

```powershell
cd research\tcmf_paper
$env:PYTHONIOENCODING = "utf-8"
& "..\..\.venv\Scripts\python" -m tcmfbench.run_eval --n 300 --out results_main
```

```powershell
& "..\..\.venv\Scripts\python" -m tcmfbench.run_mixed    --n 300 --out results_mixed
& "..\..\.venv\Scripts\python" -m tcmfbench.run_realtext --n 120 --out results_realtext  # needs Ollama
```

Outputs `RESULTS*.md` (tables) and `results*.json` (raw) per run. Synthetic runs take a few
seconds and are deterministic given `--seed`. The real-text tier needs Ollama running with
`nomic-embed-text`; it embeds each unique sentence once and caches to
`results_realtext/emb_cache.json`, so only the first run is slow.

### Realistic pool size + multi-seed harness (N01)

`run_eval.py` and `run_mixed.py` also accept `--n-distractors`, `--n-noise`, and `--seeds`
(comma-separated base seeds, e.g. `0,1,2,3,4`) to rerun any of the above at a larger candidate
pool, pooled across multiple disjoint seeds:

```powershell
& "..\..\.venv\Scripts\python" -m tcmfbench.run_eval  --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_main_scale
& "..\..\.venv\Scripts\python" -m tcmfbench.run_mixed --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_mixed_scale
```

Omitting all three flags reproduces the original small-pool, single-seed numbers bit-for-bit
(verified). See `FINDINGS.md` (N01) for what changes at the larger, more realistic pool - it is
a mixed result, not a clean win. `tcmfbench/test_n01_scale.py` unit-tests the analytic random
baseline and the seed-disjointness / no-pool-recap invariants this harness relies on.

### Confidence intervals + paired significance tests (N02)

Every `RESULTS*.md` table cell is `mean [95% bootstrap CI]` (seeded percentile bootstrap,
10000 resamples, `tcmfbench/stats.py`), and the main comparison table is followed by a paired
Wilcoxon signed-rank significance table (`tcmf_add` vs every other method, Holm-Bonferroni
corrected across the family). See `FINDINGS.md` (N02) for what this settles: a previously
unflagged significant recall@5 loss to `graph_ppr` in the mixed regime, and why N01's
recall@10 "tie" at the realistic pool is statistically significant but practically negligible.
`tcmfbench/test_stats.py` unit-tests the bootstrap CI, Wilcoxon, and Holm-Bonferroni functions
against hand-computed known answers.

### Held-out tuning split (N03)

`tcmfbench/run_tuned.py` partitions the same 5-seed protocol into a fixed, disjoint TUNE split
(seeds 0,1 - 40%) and TEST split (seeds 2,3,4 - 60%). `tcmf_add`/`tcmf_mult` lambda, RRF's `c`,
`causal_only`'s tau, and `graph_ppr`'s alpha are each swept (5 candidate values, an equal
budget per operator) on TUNE-only data, selected by mean recall@5, then every headline number
is reported on the disjoint TEST split with the selected values:

```powershell
& "..\..\.venv\Scripts\python" -m tcmfbench.run_tuned --regime pure  --n 300 --out results_main_tuned
& "..\..\.venv\Scripts\python" -m tcmfbench.run_tuned --regime mixed --n 300 --out results_mixed_tuned
```

See `FINDINGS.md` (N03) for the result: N01/N02's mixed-regime `tcmf_add` vs `graph_ppr`
recall@10 near-tie survives an honest tune/test split (it was not an artifact of eyeballing the
eval set), and the pure-regime "`graph_ppr` collapses at the realistic pool" finding narrows -
`graph_ppr`'s own alpha was never tuned before N01/N02; tuned on TUNE-only data it recovers
from 0.33 to 0.67 recall@10 (still well below `tcmf_add`'s 1.00, but a smaller gap than
previously reported). `tcmfbench/test_n03_tune_split.py` unit-tests the split contract, the
tie-break rule, and runs a small end-to-end smoke test of the sweep-then-test pipeline.

### Spurious-edge robustness (N04)

`tcmfbench/mixed.py`'s `spurious_edge_rate` injects, with probability p per scenario, one
fabricated false-ancestor edge straight into the crisis - independent of `edge_dropout`. It is
gated so a default (0.0) run draws no extra randomness and reproduces a pre-N04 scenario
byte-for-byte.

```powershell
& "..\..\.venv\Scripts\python" -m tcmfbench.run_spurious --out results_spurious
```

See `FINDINGS.md` (N04) for the result: recall degrades gracefully and never crosses below the
semantic_rag floor up to p=0.4, the real shipped retriever's favor-root weighting is
incidentally more robust to this specific (direct-edge) attack than the favor-proximate
operator-study variants - traced to a depth-1/depth-weight mechanism, not asserted - and the
precision metric this experiment introduces is already near-ceiling for every method except
`causal_only`, an honest methodological gap flagged for a future night rather than hidden.
`tcmfbench/test_n04_spurious.py` unit-tests the RNG-gating invariant, the injected edge's BFS
depth, and the precision metric against hand-computed cases.

## What the benchmark holds fixed vs varies

Fixed and honest by design: baselines and all fusion variants consume the **same** episodic
scores (from the real `MemoryStream`) and the **same** causal boosts, so any difference is
attributable to the fusion operator, not to different inputs. Varied via ablations: causal
weight lambda, similarity threshold, depth-weighting direction, and embedding difficulty
(alpha).

## Caveats

- Embeddings are synthetic (angle-mixed topic vectors), not a real text encoder. This buys full
  control of the causal-vs-semantic separation and exact ground truth; a real-text tier (Ollama
  `nomic-embed-text` over generated natural-language scenarios) is the planned follow-up.
- See `FINDINGS.md` for the open item: fusion currently ties the causal-only oracle in the pure
  regime; the mixed-regime experiment that justifies fusion over causal-only is the next task.
</content>
