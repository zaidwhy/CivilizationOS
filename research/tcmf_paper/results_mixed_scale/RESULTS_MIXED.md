# TCMF Benchmark: Mixed Regime

Scenarios: 300 per seed x 5 seed(s) = 1500 total | seeds: [0, 1, 2, 3, 4] (multi-seed, stride 100000) | chain_len: 4 | semantic_gold: 2 | distractors: 20 | noise: 55 | pool/scenario: 80 | total gold: 5 (3 causal + 2 semantic)

Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold (graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). Additive TCMF should dominate both single-signal baselines on overall recall. Means pooled across all seeds.

### Main comparison (mixed regime)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.40±0.00 | 0.40±0.00 | 0.40±0.00 | 0.00±0.00 | 1.00±0.00 | 0.02±0.01 | 51.3 |
| episodic | 0.11±0.12 | 0.16±0.14 | 0.25±0.13 | 0.00±0.00 | 0.39±0.34 | 0.02±0.01 | 53.5 |
| causal_only | 0.60±0.02 | 0.61±0.05 | 0.64±0.08 | 1.00±0.01 | 0.03±0.12 | 0.33±0.01 | 3.0 |
| graph_ppr | 0.60±0.00 | 0.80±0.01 | 0.80±0.00 | 0.67±0.01 | 1.00±0.00 | 0.04±0.00 | 25.9 |
| tcmf_mult | 0.13±0.13 | 0.19±0.15 | 0.29±0.16 | 0.06±0.13 | 0.38±0.34 | 0.02±0.01 | 43.2 |
| tcmf_add | 0.60±0.02 | 0.68±0.11 | 0.80±0.14 | 1.00±0.01 | 0.20±0.26 | 0.33±0.01 | 3.0 |
| tcmf_shipped | 0.51±0.10 | 0.61±0.14 | 0.74±0.17 | 0.86±0.16 | 0.23±0.28 | 1.00±0.00 | 1.0 |
| tcmf_rrf | 0.26±0.13 | 0.43±0.16 | 0.75±0.15 | 0.55±0.18 | 0.25±0.30 | 0.13±0.03 | 8.4 |

### Seed stability: recall@10 per individual seed (not pooled)

| seed | semantic_rag | causal_only | tcmf_add | tcmf_shipped |
|---|---|---|---|---|
| 0 | 0.40 | 0.64 | 0.79 | 0.73 |
| 1 | 0.40 | 0.63 | 0.81 | 0.76 |
| 2 | 0.40 | 0.64 | 0.80 | 0.75 |
| 3 | 0.40 | 0.63 | 0.79 | 0.74 |
| 4 | 0.40 | 0.64 | 0.81 | 0.75 |

### Additive lambda tradeoff (causal@5 vs semantic@5)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.13±0.13 | 0.19±0.15 | 0.30±0.16 | 0.06±0.13 | 0.38±0.34 | 0.03±0.01 | 38.0 |
| additive l=1 | 0.31±0.12 | 0.38±0.15 | 0.50±0.16 | 0.41±0.14 | 0.32±0.32 | 0.04±0.00 | 27.7 |
| additive l=2 | 0.45±0.08 | 0.52±0.12 | 0.63±0.15 | 0.68±0.07 | 0.27±0.30 | 0.06±0.05 | 21.4 |
| additive l=3 | 0.58±0.07 | 0.67±0.12 | 0.79±0.14 | 0.98±0.09 | 0.20±0.27 | 0.31±0.06 | 3.5 |
| additive l=4 | 0.60±0.02 | 0.68±0.11 | 0.80±0.14 | 1.00±0.01 | 0.20±0.26 | 0.33±0.01 | 3.0 |

### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| causal_only | 0.64 | 0.43 | 0.28 | 0.19 | 0.13 |
| tcmf_add | 0.80 | 0.57 | 0.41 | 0.31 | 0.25 |
