# TCMF Benchmark: Mixed Regime

Scenarios: 300 per seed x 1 seed(s) = 300 total | seeds: [0] (single-seed legacy mode) | chain_len: 4 | semantic_gold: 2 | distractors: 6 | noise: 8 | pool/scenario: 19 | total gold: 5 (3 causal + 2 semantic)

Neither signal alone recovers both gold types: `causal@5` = recall over causal-gold (graph-findable), `semantic@5` = recall over semantic-gold (similarity-findable). Additive TCMF should dominate both single-signal baselines on overall recall. Means pooled across all seeds.

### Main comparison (mixed regime)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.51 [0.50, 0.52] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.08 [0.07, 0.08] | 13.7 [13.4, 14.1] |
| episodic | 0.20 [0.19, 0.22] | 0.30 [0.28, 0.31] | 0.55 [0.53, 0.56] | 0.00 [0.00, 0.00] | 0.74 [0.70, 0.77] | 0.07 [0.07, 0.07] | 14.7 [14.5, 15.0] |
| causal_only | 0.60 [0.60, 0.60] | 0.65 [0.64, 0.66] | 0.79 [0.77, 0.80] | 1.00 [1.00, 1.00] | 0.13 [0.10, 0.16] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| graph_ppr | 0.60 [0.60, 0.60] | 0.80 [0.80, 0.80] | 0.80 [0.80, 0.80] | 0.67 [0.67, 0.67] | 1.00 [1.00, 1.00] | 0.09 [0.09, 0.09] | 11.1 [11.1, 11.2] |
| tcmf_mult | 0.22 [0.21, 0.24] | 0.33 [0.32, 0.35] | 0.74 [0.73, 0.75] | 0.08 [0.06, 0.09] | 0.71 [0.68, 0.74] | 0.08 [0.08, 0.08] | 13.4 [13.1, 13.6] |
| tcmf_add | 0.60 [0.60, 0.60] | 0.75 [0.74, 0.76] | 0.98 [0.97, 0.99] | 1.00 [1.00, 1.00] | 0.38 [0.34, 0.41] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| tcmf_shipped | 0.51 [0.50, 0.53] | 0.67 [0.66, 0.69] | 0.95 [0.94, 0.96] | 0.83 [0.81, 0.84] | 0.44 [0.41, 0.48] | 1.00 [0.99, 1.00] | 1.0 [1.0, 1.0] |
| tcmf_rrf | 0.35 [0.34, 0.37] | 0.57 [0.55, 0.58] | 0.93 [0.92, 0.94] | 0.61 [0.59, 0.63] | 0.50 [0.47, 0.54] | 0.14 [0.14, 0.14] | 7.4 [7.3, 7.6] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 21 contrasts)

Positive diff = tcmf_add higher (better for recall, worse for root_rank - lower root_rank is better). p_holm <= 0.05 is significant after correction.

| baseline | metric | mean diff | p (raw) | p (holm) |
|---|---|---|---|---|
| semantic_rag | recall@5 | +0.350 | 0.0000 | 0.0000 |
| semantic_rag | recall@10 | +0.471 | 0.0000 | 0.0000 |
| semantic_rag | root_rank | -10.710 | 0.0000 | 0.0000 |
| episodic | recall@5 | +0.455 | 0.0000 | 0.0000 |
| episodic | recall@10 | +0.430 | 0.0000 | 0.0000 |
| episodic | root_rank | -11.707 | 0.0000 | 0.0000 |
| causal_only | recall@5 | +0.098 | 0.0000 | 0.0000 |
| causal_only | recall@10 | +0.193 | 0.0000 | 0.0000 |
| causal_only | root_rank | +0.000 | 1.0000 | 1.0000 |
| graph_ppr | recall@5 | -0.050 | 0.0000 | 0.0000 |
| graph_ppr | recall@10 | +0.179 | 0.0000 | 0.0000 |
| graph_ppr | root_rank | -8.143 | 0.0000 | 0.0000 |
| tcmf_mult | recall@5 | +0.419 | 0.0000 | 0.0000 |
| tcmf_mult | recall@10 | +0.243 | 0.0000 | 0.0000 |
| tcmf_mult | root_rank | -10.353 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@5 | +0.077 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@10 | +0.034 | 0.0000 | 0.0000 |
| tcmf_shipped | root_rank | +2.000 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@5 | +0.184 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@10 | +0.051 | 0.0000 | 0.0000 |
| tcmf_rrf | root_rank | -4.430 | 0.0000 | 0.0000 |

### Additive lambda tradeoff (causal@5 vs semantic@5)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.22 [0.20, 0.23] | 0.33 [0.31, 0.34] | 0.77 [0.76, 0.78] | 0.07 [0.05, 0.08] | 0.71 [0.68, 0.75] | 0.08 [0.08, 0.08] | 12.9 [12.7, 13.0] |
| additive l=1 | 0.36 [0.35, 0.38] | 0.48 [0.47, 0.50] | 0.80 [0.80, 0.80] | 0.41 [0.39, 0.42] | 0.59 [0.56, 0.63] | 0.09 [0.09, 0.09] | 11.5 [11.4, 11.6] |
| additive l=2 | 0.48 [0.47, 0.49] | 0.60 [0.59, 0.62] | 0.84 [0.83, 0.85] | 0.68 [0.67, 0.69] | 0.49 [0.46, 0.53] | 0.10 [0.10, 0.11] | 10.3 [10.1, 10.5] |
| additive l=3 | 0.55 [0.54, 0.56] | 0.72 [0.70, 0.73] | 0.97 [0.97, 0.98] | 0.93 [0.91, 0.95] | 0.40 [0.37, 0.44] | 0.27 [0.26, 0.28] | 4.3 [4.1, 4.6] |
| additive l=4 | 0.60 [0.60, 0.60] | 0.75 [0.74, 0.76] | 0.98 [0.97, 0.99] | 1.00 [1.00, 1.00] | 0.38 [0.34, 0.41] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |

### Edge-dropout robustness (overall recall@10 vs fraction of causal edges missing)

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.51 | 0.51 | 0.51 | 0.51 | 0.51 |
| causal_only | 0.79 | 0.69 | 0.61 | 0.57 | 0.54 |
| tcmf_add | 0.98 | 0.80 | 0.66 | 0.58 | 0.55 |
