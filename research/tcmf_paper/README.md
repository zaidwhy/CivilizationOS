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
  realtext.py     natural-language scenarios across 8 crisis domains (real-text tier);
                  6 embedded and evaluated (results_realtext/), 2 authored by N05
                  (software-debugging, cybersecurity) awaiting the N06 Ollama embedding run
  embed_client.py disk-cached Ollama nomic-embed-text client
  scenario.py     scenario / memory / event data model + ground-truth labels (2 gold types)
  methods.py      baselines (random, recency, semantic RAG, episodic, causal-only, graph PPR)
                  + real TCMF retriever + additive / RRF / multiplicative operator variants
  metrics.py      recall@k, root-cause MRR/rank, nDCG@k
  stats.py        bootstrap CIs + paired Wilcoxon signed-rank + Holm-Bonferroni + Wilson score
                  interval (N11, for aggregates with only mean+n committed) (pure numpy)
  run_eval.py     pure regime: main comparison + ablations -> results_main/
  run_mixed.py    mixed regime: fusion beats single signals + dropout -> results_mixed/
  run_realtext.py real-text tier (needs Ollama) -> results_realtext/
  run_tuned.py    held-out tune/test split (N03) -> results_main_tuned/, results_mixed_tuned/
  run_spurious.py spurious false-ancestor edge robustness (N04) -> results_spurious/
  run_baselines.py 5 additional retrieval-mechanism baselines (N07, MMR/BM25/summary-buffer/
                  community-summary/extract-consolidate) -> results_baselines_pure/,
                  results_baselines_mixed/
  theory.py       formal analysis of the fusion operator (N15) - affine margin propositions
  run_theory.py   measures the propositions on real scenarios (N15) -> results_theory/
  run_lambda_sweep.py  recall@5 vs lambda, both operators, one grid (N10) -> results_lambda_sweep/
figures/          Fig 1 (causal graph) + Fig 2 (retrieval pipeline), N09; Fig 3 (fusion
                  operator margin) + Fig 4 (recall vs lambda), N10; Fig 5 (graph degradation:
                  dropout + N04 spurious edges) + Fig 6 (decision accuracy w/ Wilson CIs), N11;
                  make_figures.py regenerates all six from committed data, never hand-drawn/
                  hand-typed
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

### Additional retrieval baselines (N07)

Five more reimplementable *mechanisms* (named "X-style mechanism", not a reimplementation of
X, the same correction already applied to `graph_ppr`/HippoRAG): `rank_mmr` (maximal marginal
relevance), `rank_bm25` (lexical, no embeddings), `rank_summary_buffer` (MemGPT-style recent
window + paged archival summary), `rank_community_summary` (GraphRAG-style cluster-then-
retrieve-by-summary), `rank_extract_consolidate` (Mem0-style dedupe/merge before ranking) - all
in `tcmfbench/methods.py`. Each one's single hyperparameter is swept on the N03 TUNE split
(equal 5-candidate budget) and reported on the disjoint TEST split, alongside the 10
pre-existing methods at their N03-tuned values:

```powershell
& "..\..\.venv\Scripts\python" -m tcmfbench.run_baselines --regime pure  --out results_baselines_pure
& "..\..\.venv\Scripts\python" -m tcmfbench.run_baselines --regime mixed --out results_baselines_mixed
```

See `FINDINGS.md` (N07) for the result: none of the 5 new baselines ever meaningfully recovers
a causal ancestor (`causal@5` <= 0.05 in both regimes, vs TCMF's 1.00) - TCMF's margin is not
an artifact of weak baseline choice. In the pure regime specifically, 3 of the 5
(`bm25`/`community_summary`/`extract_consolidate`) fail to beat even a `random` baseline on any
metric; traced to a real, deterministic property of each mechanism against this benchmark's
adversarial construction, not an implementation bug (all 5 beat `random` comfortably in the
mixed regime). `tcmfbench/test_n07_baselines.py` (16 tests) unit-tests each mechanism against
hand-computed cases, including an exact MMR tie-breaking construction and a hand-derived BM25
score.

### Fig 1 (causal graph) + Fig 2 (retrieval pipeline) (N09)

`figures/make_figures.py` regenerates both figures from committed data - never hand-drawn,
never hand-typed:

```powershell
& "..\..\.venv\Scripts\python" figures\make_figures.py --out figures
```

Fig 1 is drawn from a small scenario generated by the real `tcmfbench.generator.generate`
(dumped to the committed `figures/fig1_scenario.json`, then re-loaded from that file before
drawing, so the rendered labels are provably the committed data): the causal chain (root
cause -> decision -> crisis) with its witness memories, and the distractors sitting off the
causal path, annotated with the real cosine similarities computed from that scenario's
embeddings (root-cause witness vs. crisis is semantically far; a distractor vs. crisis is
semantically near). Fig 2 is a schematic of `TCMFRetriever.retrieve()`'s real pipeline stages
(episodic stream + bounded backward BFS / causal-boost stream converging into the fusion box);
`tcmfbench/test_n09_figures.py` checks its box text against literal phrases pulled from
`api/memory/tcmf.py` and `api/memory/causal_graph.py`, so the diagram cannot silently drift
from the shipped retriever. Requires `matplotlib` (`research/tcmf_paper/requirements-bench.txt`,
not needed for anything else in this package).

### Fig 3 (fusion operator) + Fig 4 (recall vs lambda) (N10)

Same `figures/make_figures.py` command as above also produces these two; Fig 4 additionally
needs `results_lambda_sweep/` to exist first (`python -m tcmfbench.run_lambda_sweep --n 300
--n-seeds 5 --out results_lambda_sweep`, ~2 min).

Fig 3 draws `theory.py`'s affine margin-vs-lambda mechanism (Propositions 1-2) on 10 real
(root cause, hardest distractor) pairs, one per `results_theory/`-protocol scenario: the
multiplicative panel's zero-crossings scatter from lambda 3.11 to 9.26 with one pair that never
crosses at all, while the additive panel's crossings all sit left of one shared, episodic-score-
independent bound (3.64) that the shipped lambda=4 clears. Fig 4 plots recall@5 vs lambda for
both operators on one shared 16-point grid with N02 bootstrap CI bands, from
`tcmfbench/run_lambda_sweep.py` (new) - the multiplicative curve is genuinely flat through
lambda~0.3 (shaded) and then rises, reaching 0.52 at the N03 tune-selected value 2.4 (marked),
so the figure does not imply multiplicative fusion is flat everywhere, only that a small-lambda
sweep would never find the fix. `tcmfbench/test_n10_figures.py` (15 tests) checks both against
the real theory functions and the committed result JSON, not hand-typed numbers.

### Fig 5 (graph degradation) + Fig 6 (decision accuracy) (N11)

Same `figures/make_figures.py` command as above also produces these two; both are a pure
plotting job over already-committed data (`results_spurious/`, `results_mixed_scale/`,
`results_decision/`) - no new experiment.

Fig 5 has two panels sharing one recall@10 axis: (a) `results_mixed_scale/results_mixed.json`'s
`dropout_curve` (missing edges, 0 to 100%) and (b) `results_spurious/results_spurious.json`'s
`curve` (N04's false-ancestor edges, dropout=0, with N02 bootstrap CI bands). `semantic_rag` is
flat at 0.40 in both - drawn as a dashed "semantic floor" reference line rather than another
solid curve, since it never reads the causal graph at all. `tcmf_add` degrades under dropout
(0.80 -> 0.25) but is essentially flat under spurious edges alone (0.80 -> 0.76 at p=0.4) and
never drops below the semantic floor in either panel - matching N04's own reported crossover
("never"). Fig 6 plots decision accuracy (LLM council picking the true root cause, N06/W1) per
method as a Wilson 95% score interval, with `no_retrieval` (0.32 [0.21, 0.44]) and `oracle`
(0.95 [0.86, 0.98]) as dashed/dotted reference lines. `results_decision/results_decision.json`
only stores the aggregate `(mean, std, n)` per method, not a per-scenario array to bootstrap
over; since `decision_acc` is exactly `k/n` for some integer `k`, `k` is recovered exactly from
the committed mean, and `tcmfbench.stats.wilson_ci` (new, N11 - closed-form, unit-tested against
Newcombe 1998's published table) gives a proper CI from `(k, n)` alone. The causal-recall
methods (`causal_only` 0.85, `tcmf_add` 0.83, `tcmf_shipped` 0.97) sit clearly above the floor
toward the ceiling; the pure-symptom baselines (`semantic_rag` 0.35, `episodic` 0.25) sit near
the floor; the broken `tcmf_mult` (0.50) lands in between - the same story RESULTS_DECISION.md
already told, now with CIs instead of bare means. `tcmfbench/test_n11_figures.py` (13 tests)
checks both figures against the committed source JSON and cross-checks the Wilson CI values
independently, not hand-typed numbers.

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
