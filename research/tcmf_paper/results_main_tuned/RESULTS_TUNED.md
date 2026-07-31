# TCMF Benchmark: pure regime, held-out tuning split (N03)

tune seeds: (0, 1) (n=300 each, 600 scenarios) | test seeds: (2, 3, 4) (n=300 each, 900 scenarios) | stride: 100000 | pool/scenario: 78 | selection metric: recall@5 (TUNE only)

Every hyperparameter below (tcmf_add lambda, tcmf_mult lambda, RRF c, causal_only tau, graph_ppr alpha) is selected using ONLY the tune split, then every table below is computed on the disjoint test split with the selected values plugged in. The test split was never inspected while selecting.

### N03 tune-set hyperparameter sweep (recall@5, mean over TUNE split only, budget=5 candidates/operator)

| operator | candidate | tune recall@5 | selected |
|---|---|---|---|
| tcmf_add_lambda | 0.5 | 0.0122 | |
| tcmf_add_lambda | 1.0 | 0.3633 | |
| tcmf_add_lambda | 2.0 | 0.6717 | |
| tcmf_add_lambda | 4.0 | 0.9994 **<-selected** | |
| tcmf_add_lambda | 8.0 | 0.9994 | |
| tcmf_mult_lambda | 0.1 | 0.0000 | |
| tcmf_mult_lambda | 0.3 | 0.0000 | |
| tcmf_mult_lambda | 0.6 | 0.0089 | |
| tcmf_mult_lambda | 1.2 | 0.2200 | |
| tcmf_mult_lambda | 2.4 | 0.5278 **<-selected** | |
| rrf_c | 2.0 | 0.7272 **<-selected** | |
| rrf_c | 5.0 | 0.6611 | |
| rrf_c | 10.0 | 0.5628 | |
| rrf_c | 20.0 | 0.4383 | |
| rrf_c | 40.0 | 0.3256 | |
| causal_only_tau | 0.3 | 0.9783 | |
| causal_only_tau | 0.45 | 0.9994 | |
| causal_only_tau | 0.6 | 1.0000 **<-selected** | |
| causal_only_tau | 0.75 | 1.0000 | |
| causal_only_tau | 0.9 | 0.0683 | |
| graph_ppr_alpha | 0.5 | 0.0000 | |
| graph_ppr_alpha | 0.65 | 0.0000 | |
| graph_ppr_alpha | 0.75 | 0.0661 | |
| graph_ppr_alpha | 0.85 | 0.3333 | |
| graph_ppr_alpha | 0.95 | 0.6667 **<-selected** | |

| operator | selected value |
|---|---|
| tcmf_add_lambda | 4.0 |
| tcmf_mult_lambda | 2.4 |
| rrf_c | 2.0 |
| causal_only_tau | 0.6 |
| graph_ppr_alpha | 0.95 |

### Main comparison (TEST split only, tune-selected hyperparameters)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| random | 0.01 [0.01, 0.02] | 0.04 [0.03, 0.05] | 0.07 [0.06, 0.08] | 0.14 [0.12, 0.15] | 0.07 [0.06, 0.08] | 38.6 [37.1, 40.1] | 0.08 [0.07, 0.09] |
| recency | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.01] | 0.02 [0.01, 0.02] | 0.02 [0.02, 0.02] | 65.9 [65.3, 66.5] | 0.01 [0.01, 0.01] |
| semantic_rag | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.02 [0.02, 0.02] | 50.0 [48.9, 51.2] | 0.00 [0.00, 0.00] |
| episodic | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.02 [0.02, 0.02] | 51.8 [51.1, 52.5] | 0.00 [0.00, 0.00] |
| causal_only | 0.33 [0.33, 0.33] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] | 0.84 [0.84, 0.84] |
| graph_ppr | 0.33 [0.33, 0.33] | 0.67 [0.67, 0.67] | 0.67 [0.67, 0.67] | 0.67 [0.67, 0.67] | 0.04 [0.04, 0.04] | 23.1 [23.1, 23.1] | 0.52 [0.52, 0.52] |
| tcmf_mult | 0.33 [0.32, 0.33] | 0.51 [0.50, 0.52] | 0.52 [0.51, 0.53] | 0.54 [0.52, 0.55] | 0.04 [0.04, 0.04] | 24.7 [24.4, 25.0] | 0.43 [0.43, 0.44] |
| tcmf_add | 0.33 [0.33, 0.33] | 1.00 [0.99, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] | 0.84 [0.84, 0.84] |
| tcmf_shipped | 0.33 [0.33, 0.33] | 0.77 [0.76, 0.78] | 0.80 [0.79, 0.81] | 0.83 [0.82, 0.84] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.0] | 0.91 [0.90, 0.91] |
| tcmf_rrf | 0.20 [0.19, 0.21] | 0.47 [0.46, 0.48] | 0.73 [0.72, 0.73] | 1.00 [1.00, 1.00] | 0.16 [0.16, 0.16] | 6.3 [6.2, 6.3] | 0.64 [0.64, 0.65] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 18 contrasts)

Positive diff = tcmf_add higher (better for recall, worse for root_rank - lower root_rank is better). p_holm <= 0.05 is significant after correction.

| baseline | metric | mean diff | p (raw) | p (holm) |
|---|---|---|---|---|
| random | recall@5 | +0.932 | 0.0000 | 0.0000 |
| random | root_rank | -35.564 | 0.0000 | 0.0000 |
| recency | recall@5 | +0.993 | 0.0000 | 0.0000 |
| recency | root_rank | -62.911 | 0.0000 | 0.0000 |
| semantic_rag | recall@5 | +1.000 | 0.0000 | 0.0000 |
| semantic_rag | root_rank | -47.020 | 0.0000 | 0.0000 |
| episodic | recall@5 | +1.000 | 0.0000 | 0.0000 |
| episodic | root_rank | -48.814 | 0.0000 | 0.0000 |
| causal_only | recall@5 | +0.000 | 1.0000 | 1.0000 |
| causal_only | root_rank | +0.010 | 0.0083 | 0.0167 |
| graph_ppr | recall@5 | +0.333 | 0.0000 | 0.0000 |
| graph_ppr | root_rank | -20.076 | 0.0000 | 0.0000 |
| tcmf_mult | recall@5 | +0.481 | 0.0000 | 0.0000 |
| tcmf_mult | root_rank | -21.687 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@5 | +0.203 | 0.0000 | 0.0000 |
| tcmf_shipped | root_rank | +2.010 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@5 | +0.274 | 0.0000 | 0.0000 |
| tcmf_rrf | root_rank | -3.256 | 0.0000 | 0.0000 |

### Headline-ordering check vs N01 (recall@10, descending)

| rank | N01 (pooled, all 5 seeds, untuned lambda/tau) | N03 test-only (3 seeds, tune-selected lambda/tau) |
|---|---|---|
| 1 | causal_only | causal_only |
| 2 | tcmf_add | tcmf_add |
| 3 | tcmf_rrf | tcmf_rrf |
| 4 | tcmf_shipped | tcmf_shipped |
| 5 | graph_ppr | graph_ppr |
| 6 | random | tcmf_mult |
| 7 | recency | random |
| 8 | tcmf_mult | recency |
| 9 | semantic_rag | semantic_rag |
| 10 | episodic | episodic |

Ordering CHANGED from N01 (see ranks above) - this is the honest N03 result, not smoothed over.
