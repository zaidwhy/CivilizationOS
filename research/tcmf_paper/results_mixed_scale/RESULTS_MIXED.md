# TCMF Benchmark: Mixed Regime

Scenarios: 300 per seed x 5 seed(s) = 1500 total | seeds: [0, 1, 2, 3, 4] (multi-seed, stride 100000) | chain_len: 4 | semantic_gold: 2 | distractors: 20 | noise: 55 | pool/scenario: 80 | total gold: 5 (3 causal + 2 semantic)

Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold (graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). Additive TCMF should dominate both single-signal baselines on overall recall. Means pooled across all seeds.

### Main comparison (mixed regime)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.02 [0.02, 0.02] | 51.3 [50.5, 52.2] |
| episodic | 0.11 [0.10, 0.12] | 0.16 [0.15, 0.16] | 0.25 [0.24, 0.25] | 0.00 [0.00, 0.00] | 0.39 [0.38, 0.41] | 0.02 [0.02, 0.02] | 53.5 [52.9, 54.0] |
| causal_only | 0.60 [0.60, 0.60] | 0.61 [0.61, 0.62] | 0.64 [0.63, 0.64] | 1.00 [1.00, 1.00] | 0.03 [0.03, 0.04] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| graph_ppr | 0.60 [0.60, 0.60] | 0.80 [0.80, 0.80] | 0.80 [0.80, 0.80] | 0.67 [0.67, 0.67] | 1.00 [1.00, 1.00] | 0.04 [0.04, 0.04] | 25.9 [25.8, 26.0] |
| tcmf_mult | 0.13 [0.13, 0.14] | 0.19 [0.18, 0.20] | 0.29 [0.28, 0.30] | 0.06 [0.05, 0.07] | 0.38 [0.36, 0.40] | 0.02 [0.02, 0.03] | 43.2 [42.7, 43.8] |
| tcmf_add | 0.60 [0.60, 0.60] | 0.68 [0.67, 0.68] | 0.80 [0.79, 0.81] | 1.00 [1.00, 1.00] | 0.20 [0.19, 0.21] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| tcmf_shipped | 0.51 [0.51, 0.52] | 0.61 [0.60, 0.62] | 0.74 [0.74, 0.75] | 0.86 [0.86, 0.87] | 0.23 [0.21, 0.24] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.0] |
| tcmf_rrf | 0.26 [0.26, 0.27] | 0.43 [0.42, 0.44] | 0.75 [0.74, 0.76] | 0.55 [0.54, 0.56] | 0.25 [0.24, 0.27] | 0.13 [0.12, 0.13] | 8.4 [8.3, 8.4] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 21 contrasts)

Positive diff = tcmf_add higher (better for recall, worse for root_rank - lower root_rank is better). p_holm <= 0.05 is significant after correction.

| baseline | metric | mean diff | p (raw) | p (holm) |
|---|---|---|---|---|
| semantic_rag | recall@5 | +0.279 | 0.0000 | 0.0000 |
| semantic_rag | recall@10 | +0.398 | 0.0000 | 0.0000 |
| semantic_rag | root_rank | -48.311 | 0.0000 | 0.0000 |
| episodic | recall@5 | +0.522 | 0.0000 | 0.0000 |
| episodic | recall@10 | +0.551 | 0.0000 | 0.0000 |
| episodic | root_rank | -50.447 | 0.0000 | 0.0000 |
| causal_only | recall@5 | +0.067 | 0.0000 | 0.0000 |
| causal_only | recall@10 | +0.161 | 0.0000 | 0.0000 |
| causal_only | root_rank | +0.001 | 0.5862 | 0.5862 |
| graph_ppr | recall@5 | -0.121 | 0.0000 | 0.0000 |
| graph_ppr | recall@10 | -0.002 | 0.0000 | 0.0000 |
| graph_ppr | root_rank | -22.869 | 0.0000 | 0.0000 |
| tcmf_mult | recall@5 | +0.491 | 0.0000 | 0.0000 |
| tcmf_mult | recall@10 | +0.506 | 0.0000 | 0.0000 |
| tcmf_mult | root_rank | -40.204 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@5 | +0.071 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@10 | +0.053 | 0.0000 | 0.0000 |
| tcmf_shipped | root_rank | +2.013 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@5 | +0.250 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@10 | +0.048 | 0.0000 | 0.0000 |
| tcmf_rrf | root_rank | -5.343 | 0.0000 | 0.0000 |

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
| additive l=0.5 | 0.13 [0.13, 0.14] | 0.19 [0.18, 0.20] | 0.30 [0.29, 0.31] | 0.06 [0.05, 0.07] | 0.38 [0.36, 0.40] | 0.03 [0.03, 0.03] | 38.0 [37.5, 38.5] |
| additive l=1 | 0.31 [0.30, 0.32] | 0.38 [0.37, 0.38] | 0.50 [0.49, 0.50] | 0.41 [0.40, 0.42] | 0.32 [0.31, 0.34] | 0.04 [0.04, 0.04] | 27.7 [27.5, 27.9] |
| additive l=2 | 0.45 [0.44, 0.45] | 0.52 [0.51, 0.52] | 0.63 [0.63, 0.64] | 0.68 [0.68, 0.69] | 0.27 [0.26, 0.29] | 0.06 [0.06, 0.06] | 21.4 [21.1, 21.7] |
| additive l=3 | 0.58 [0.57, 0.58] | 0.67 [0.66, 0.67] | 0.79 [0.79, 0.80] | 0.98 [0.97, 0.98] | 0.20 [0.19, 0.22] | 0.31 [0.31, 0.31] | 3.5 [3.5, 3.6] |
| additive l=4 | 0.60 [0.60, 0.60] | 0.68 [0.67, 0.68] | 0.80 [0.79, 0.81] | 1.00 [1.00, 1.00] | 0.20 [0.19, 0.21] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |

### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| causal_only | 0.64 | 0.43 | 0.28 | 0.19 | 0.13 |
| tcmf_add | 0.80 | 0.57 | 0.41 | 0.31 | 0.25 |
