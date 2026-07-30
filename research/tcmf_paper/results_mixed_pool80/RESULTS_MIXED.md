# TCMF Benchmark: Mixed Regime

Scenarios: 300 per seed | seeds: [0, 1, 2, 3, 4] (5x300 = 1500 total) | chain_len: 4 | semantic_gold: 2 | distractors: 20 | noise: 55 | pool size: 80 | total gold: 5 (3 causal + 2 semantic)

Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold (graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). Additive TCMF should dominate both single-signal baselines on overall recall. Main comparison pools scenarios across all seeds before computing mean/std; the lambda tradeoff and dropout curve below use seed[0] only.

### Main comparison (mixed regime)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| random | 0.04±0.08 | 0.06±0.11 | 0.13±0.14 | 0.06±0.14 | 0.07±0.17 | 0.06±0.12 | 40.8 |
| semantic_rag | 0.40±0.00 | 0.40±0.00 | 0.40±0.00 | 0.00±0.00 | 1.00±0.00 | 0.02±0.01 | 50.5 |
| episodic | 0.10±0.12 | 0.14±0.13 | 0.24±0.13 | 0.00±0.00 | 0.36±0.34 | 0.02±0.00 | 52.8 |
| causal_only | 0.60±0.03 | 0.61±0.05 | 0.64±0.09 | 1.00±0.00 | 0.03±0.13 | 0.33±0.01 | 3.0 |
| graph_ppr | 0.60±0.00 | 0.80±0.00 | 0.80±0.00 | 0.67±0.00 | 1.00±0.00 | 0.04±0.00 | 25.8 |
| tcmf_mult | 0.12±0.13 | 0.17±0.14 | 0.28±0.15 | 0.04±0.11 | 0.35±0.33 | 0.03±0.01 | 42.9 |
| tcmf_add | 0.60±0.03 | 0.67±0.10 | 0.79±0.14 | 1.00±0.00 | 0.18±0.26 | 0.33±0.01 | 3.0 |
| tcmf_shipped | 0.50±0.10 | 0.59±0.14 | 0.73±0.17 | 0.84±0.17 | 0.21±0.27 | 1.00±0.00 | 1.0 |
| tcmf_rrf | 0.27±0.12 | 0.42±0.15 | 0.74±0.15 | 0.54±0.18 | 0.24±0.29 | 0.12±0.03 | 8.4 |

### Main comparison recall@10, per seed (stability check)

| method | seed=0 | seed=1 | seed=2 | seed=3 | seed=4 | pooled |
|---|---|---|---|---|---|---|
| random | 0.13 | 0.13 | 0.13 | 0.14 | 0.13 | 0.13 |
| semantic_rag | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| episodic | 0.25 | 0.25 | 0.24 | 0.25 | 0.24 | 0.24 |
| causal_only | 0.64 | 0.64 | 0.64 | 0.64 | 0.64 | 0.64 |
| graph_ppr | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 |
| tcmf_mult | 0.28 | 0.28 | 0.28 | 0.28 | 0.28 | 0.28 |
| tcmf_add | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 |
| tcmf_shipped | 0.73 | 0.73 | 0.73 | 0.73 | 0.73 | 0.73 |
| tcmf_rrf | 0.74 | 0.74 | 0.74 | 0.74 | 0.74 | 0.74 |

### Random-baseline sanity check (analytic vs measured)

pool size = 5 gold + 20 distractors + 55 noise = 80

| k | analytic E[recall@k] = k/pool | measured (random, pooled) |
|---|---|---|
| 3 | 0.037 | 0.037 |
| 5 | 0.062 | 0.063 |
| 10 | 0.125 | 0.134 |

### Additive lambda tradeoff (causal@5 vs semantic@5)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.12±0.13 | 0.17±0.15 | 0.29±0.15 | 0.05±0.12 | 0.34±0.33 | 0.03±0.01 | 37.6 |
| additive l=1 | 0.30±0.12 | 0.36±0.15 | 0.48±0.16 | 0.40±0.13 | 0.29±0.32 | 0.04±0.00 | 27.5 |
| additive l=2 | 0.44±0.08 | 0.51±0.12 | 0.62±0.15 | 0.68±0.07 | 0.25±0.30 | 0.06±0.05 | 21.2 |
| additive l=3 | 0.58±0.07 | 0.66±0.12 | 0.78±0.14 | 0.98±0.09 | 0.18±0.26 | 0.31±0.06 | 3.6 |
| additive l=4 | 0.60±0.03 | 0.67±0.11 | 0.79±0.14 | 1.00±0.00 | 0.18±0.26 | 0.33±0.01 | 3.0 |

### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.51 | 0.51 | 0.51 | 0.51 | 0.51 |
| causal_only | 0.79 | 0.69 | 0.61 | 0.57 | 0.54 |
| tcmf_add | 0.98 | 0.80 | 0.66 | 0.58 | 0.55 |
