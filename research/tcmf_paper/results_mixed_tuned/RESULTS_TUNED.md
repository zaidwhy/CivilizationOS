# TCMF Benchmark: mixed regime, held-out tuning split (N03)

tune seeds: (0, 1) (n=300 each, 600 scenarios) | test seeds: (2, 3, 4) (n=300 each, 900 scenarios) | stride: 100000 | pool/scenario: 80 | selection metric: recall@5 (TUNE only)

Every hyperparameter below (tcmf_add lambda, tcmf_mult lambda, RRF c, causal_only tau, graph_ppr alpha) is selected using ONLY the tune split, then every table below is computed on the disjoint test split with the selected values plugged in. The test split was never inspected while selecting.

### N03 tune-set hyperparameter sweep (recall@5, mean over TUNE split only, budget=5 candidates/operator)

| operator | candidate | tune recall@5 | selected |
|---|---|---|---|
| tcmf_add_lambda | 0.5 | 0.1830 | |
| tcmf_add_lambda | 1.0 | 0.3747 | |
| tcmf_add_lambda | 2.0 | 0.5180 | |
| tcmf_add_lambda | 4.0 | 0.6730 **<-selected** | |
| tcmf_add_lambda | 8.0 | 0.6723 | |
| tcmf_mult_lambda | 0.1 | 0.1550 | |
| tcmf_mult_lambda | 0.3 | 0.1557 | |
| tcmf_mult_lambda | 0.6 | 0.1820 | |
| tcmf_mult_lambda | 1.2 | 0.3173 | |
| tcmf_mult_lambda | 2.4 | 0.4710 **<-selected** | |
| rrf_c | 2.0 | 0.5353 **<-selected** | |
| rrf_c | 5.0 | 0.4983 | |
| rrf_c | 10.0 | 0.4267 | |
| rrf_c | 20.0 | 0.3390 | |
| rrf_c | 40.0 | 0.2773 | |
| causal_only_tau | 0.3 | 0.5923 | |
| causal_only_tau | 0.45 | 0.6120 | |
| causal_only_tau | 0.6 | 0.6123 **<-selected** | |
| causal_only_tau | 0.75 | 0.6123 | |
| causal_only_tau | 0.9 | 0.0687 | |
| graph_ppr_alpha | 0.5 | 0.4000 | |
| graph_ppr_alpha | 0.65 | 0.5923 | |
| graph_ppr_alpha | 0.75 | 0.6000 | |
| graph_ppr_alpha | 0.85 | 0.7997 **<-selected** | |
| graph_ppr_alpha | 0.95 | 0.7993 | |

| operator | selected value |
|---|---|
| tcmf_add_lambda | 4.0 |
| tcmf_mult_lambda | 2.4 |
| rrf_c | 2.0 |
| causal_only_tau | 0.6 |
| graph_ppr_alpha | 0.85 |

### Main comparison (TEST split only, tune-selected hyperparameters)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.02 [0.02, 0.02] | 51.3 [50.2, 52.4] |
| episodic | 0.11 [0.10, 0.12] | 0.16 [0.15, 0.17] | 0.25 [0.24, 0.26] | 0.00 [0.00, 0.00] | 0.40 [0.37, 0.42] | 0.02 [0.02, 0.02] | 53.6 [52.8, 54.3] |
| causal_only | 0.60 [0.60, 0.60] | 0.61 [0.61, 0.62] | 0.64 [0.63, 0.64] | 1.00 [1.00, 1.00] | 0.03 [0.03, 0.04] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| graph_ppr | 0.60 [0.60, 0.60] | 0.80 [0.80, 0.80] | 0.80 [0.80, 0.80] | 0.67 [0.67, 0.67] | 1.00 [1.00, 1.00] | 0.04 [0.04, 0.04] | 25.8 [25.8, 25.9] |
| tcmf_mult | 0.40 [0.40, 0.41] | 0.47 [0.46, 0.48] | 0.59 [0.58, 0.60] | 0.60 [0.59, 0.61] | 0.29 [0.27, 0.31] | 0.05 [0.04, 0.05] | 25.7 [25.4, 26.1] |
| tcmf_add | 0.60 [0.60, 0.60] | 0.68 [0.68, 0.69] | 0.80 [0.79, 0.81] | 1.00 [1.00, 1.00] | 0.21 [0.19, 0.23] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| tcmf_shipped | 0.52 [0.51, 0.52] | 0.61 [0.60, 0.62] | 0.74 [0.73, 0.76] | 0.87 [0.86, 0.88] | 0.23 [0.22, 0.25] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.0] |
| tcmf_rrf | 0.34 [0.34, 0.35] | 0.54 [0.53, 0.55] | 0.77 [0.76, 0.78] | 0.72 [0.71, 0.73] | 0.26 [0.24, 0.28] | 0.16 [0.16, 0.16] | 6.3 [6.2, 6.4] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 21 contrasts)

Positive diff = tcmf_add higher (better for recall, worse for root_rank - lower root_rank is better). p_holm <= 0.05 is significant after correction.

| baseline | metric | mean diff | p (raw) | p (holm) |
|---|---|---|---|---|
| semantic_rag | recall@5 | +0.284 | 0.0000 | 0.0000 |
| semantic_rag | recall@10 | +0.398 | 0.0000 | 0.0000 |
| semantic_rag | root_rank | -48.308 | 0.0000 | 0.0000 |
| episodic | recall@5 | +0.525 | 0.0000 | 0.0000 |
| episodic | recall@10 | +0.549 | 0.0000 | 0.0000 |
| episodic | root_rank | -50.559 | 0.0000 | 0.0000 |
| causal_only | recall@5 | +0.070 | 0.0000 | 0.0000 |
| causal_only | recall@10 | +0.160 | 0.0000 | 0.0000 |
| causal_only | root_rank | +0.010 | 0.0083 | 0.0083 |
| graph_ppr | recall@5 | -0.116 | 0.0000 | 0.0000 |
| graph_ppr | recall@10 | -0.002 | 0.0000 | 0.0000 |
| graph_ppr | root_rank | -22.826 | 0.0000 | 0.0000 |
| tcmf_mult | recall@5 | +0.209 | 0.0000 | 0.0000 |
| tcmf_mult | recall@10 | +0.209 | 0.0000 | 0.0000 |
| tcmf_mult | root_rank | -22.739 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@5 | +0.070 | 0.0000 | 0.0000 |
| tcmf_shipped | recall@10 | +0.053 | 0.0000 | 0.0000 |
| tcmf_shipped | root_rank | +2.010 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@5 | +0.145 | 0.0000 | 0.0000 |
| tcmf_rrf | recall@10 | +0.028 | 0.0000 | 0.0000 |
| tcmf_rrf | root_rank | -3.294 | 0.0000 | 0.0000 |

### Headline-ordering check vs N01 (recall@10, descending)

| rank | N01 (pooled, all 5 seeds, untuned lambda/tau) | N03 test-only (3 seeds, tune-selected lambda/tau) |
|---|---|---|
| 1 | graph_ppr | graph_ppr |
| 2 | tcmf_add | tcmf_add |
| 3 | tcmf_rrf | tcmf_rrf |
| 4 | tcmf_shipped | tcmf_shipped |
| 5 | causal_only | causal_only |
| 6 | semantic_rag | tcmf_mult |
| 7 | tcmf_mult | semantic_rag |
| 8 | episodic | episodic |

Ordering CHANGED from N01 (see ranks above) - this is the honest N03 result, not smoothed over.
