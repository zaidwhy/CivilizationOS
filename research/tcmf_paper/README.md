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
  run_eval.py     pure regime: main comparison + ablations -> results_main/
  run_mixed.py    mixed regime: fusion beats single signals + dropout -> results_mixed/
  run_realtext.py real-text tier (needs Ollama) -> results_realtext/
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
