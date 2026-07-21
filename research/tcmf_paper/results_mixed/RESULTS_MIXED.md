# TCMF Benchmark: Mixed Regime

Scenarios: 300 | seed: 0 | chain_len: 4 | semantic_gold: 2 | distractors: 6 | noise: 8 | total gold: 5 (3 causal + 2 semantic)

Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold (graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). Additive TCMF should dominate both single-signal baselines on overall recall.

### Main comparison (mixed regime)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.40±0.00 | 0.40±0.00 | 0.51±0.12 | 0.00±0.00 | 1.00±0.00 | 0.08±0.02 | 13.7 |
| episodic | 0.20±0.13 | 0.30±0.12 | 0.55±0.13 | 0.00±0.00 | 0.74±0.30 | 0.07±0.01 | 14.7 |
| causal_only | 0.60±0.01 | 0.65±0.09 | 0.79±0.14 | 1.00±0.00 | 0.13±0.23 | 0.33±0.00 | 3.0 |
| graph_ppr | 0.60±0.00 | 0.80±0.00 | 0.80±0.01 | 0.67±0.00 | 1.00±0.00 | 0.09±0.00 | 11.1 |
| tcmf_mult | 0.22±0.14 | 0.33±0.14 | 0.74±0.10 | 0.08±0.14 | 0.71±0.31 | 0.08±0.01 | 13.4 |
| tcmf_add | 0.60±0.01 | 0.75±0.12 | 0.98±0.06 | 1.00±0.00 | 0.38±0.30 | 0.33±0.00 | 3.0 |
| tcmf_shipped | 0.51±0.10 | 0.67±0.15 | 0.95±0.09 | 0.83±0.17 | 0.44±0.32 | 1.00±0.03 | 1.0 |
| tcmf_rrf | 0.35±0.13 | 0.57±0.14 | 0.93±0.10 | 0.61±0.16 | 0.50±0.32 | 0.14±0.03 | 7.4 |

### Additive lambda tradeoff (causal@5 vs semantic@5)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.22±0.14 | 0.33±0.14 | 0.77±0.07 | 0.07±0.13 | 0.71±0.30 | 0.08±0.01 | 12.9 |
| additive l=1 | 0.36±0.12 | 0.48±0.14 | 0.80±0.00 | 0.41±0.14 | 0.59±0.32 | 0.09±0.01 | 11.5 |
| additive l=2 | 0.48±0.10 | 0.60±0.14 | 0.84±0.08 | 0.68±0.06 | 0.49±0.34 | 0.10±0.04 | 10.3 |
| additive l=3 | 0.55±0.09 | 0.72±0.14 | 0.97±0.07 | 0.93±0.14 | 0.40±0.31 | 0.27±0.08 | 4.3 |
| additive l=4 | 0.60±0.01 | 0.75±0.12 | 0.98±0.06 | 1.00±0.00 | 0.38±0.30 | 0.33±0.00 | 3.0 |

### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.51 | 0.51 | 0.51 | 0.51 | 0.51 |
| causal_only | 0.79 | 0.69 | 0.61 | 0.57 | 0.54 |
| tcmf_add | 0.98 | 0.80 | 0.66 | 0.58 | 0.55 |
