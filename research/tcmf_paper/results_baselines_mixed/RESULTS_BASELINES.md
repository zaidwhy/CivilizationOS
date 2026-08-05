# TCMF Benchmark: mixed regime, N07 additional retrieval baselines

tune seeds: (0, 1) (n=300 each) | test seeds: (2, 3, 4) (n=300 each) | stride: 100000 | pool/scenario: 80 | pre-existing-method hyperparameters: N03-tuned (loaded from results_mixed_tuned, not re-derived) | new-baseline hyperparameters: swept here on TUNE only, budget=5/operator, selection metric recall@5

New baselines are reimplementable *mechanisms*, not system reimplementations: `mmr` (maximal marginal relevance), `bm25` (lexical, no embeddings), `summary_buffer` (MemGPT-style recent window + paged archival summary), `community_summary` (GraphRAG-style cluster-then-retrieve), `extract_consolidate` (Mem0-style dedupe/merge before ranking). All 5 evaluated on the TEST split only.

### N07 tune-set hyperparameter sweep for the 5 new baselines (recall@5, mean over TUNE split only, budget=5 candidates/operator - same protocol N03 used)

| operator | candidate | tune recall@5 | selected |
|---|---|---|---|
| mmr_lambda | 0.1 | 0.2613 | |
| mmr_lambda | 0.3 | 0.2610 | |
| mmr_lambda | 0.5 | 0.2253 | |
| mmr_lambda | 0.7 | 0.4000 **<-selected** | |
| mmr_lambda | 0.9 | 0.4000 | |
| bm25_k1 | 0.5 | 0.4193 **<-selected** | |
| bm25_k1 | 1.0 | 0.4193 | |
| bm25_k1 | 1.5 | 0.4193 | |
| bm25_k1 | 2.0 | 0.4193 | |
| bm25_k1 | 2.5 | 0.4193 | |
| summary_buffer_window | 5 | 0.0230 **<-selected** | |
| summary_buffer_window | 10 | 0.0230 | |
| summary_buffer_window | 20 | 0.0230 | |
| summary_buffer_window | 40 | 0.0230 | |
| summary_buffer_window | 60 | 0.0230 | |
| community_n | 2 | 0.3990 **<-selected** | |
| community_n | 4 | 0.3987 | |
| community_n | 6 | 0.3920 | |
| community_n | 8 | 0.3833 | |
| community_n | 12 | 0.3760 | |
| consolidate_threshold | 0.8 | 0.4000 **<-selected** | |
| consolidate_threshold | 0.85 | 0.4000 | |
| consolidate_threshold | 0.9 | 0.4000 | |
| consolidate_threshold | 0.95 | 0.4000 | |
| consolidate_threshold | 0.98 | 0.4000 | |

| operator | selected value |
|---|---|
| mmr_lambda | 0.7 |
| bm25_k1 | 0.5 |
| summary_buffer_window | 5 |
| community_n | 2 |
| consolidate_threshold | 0.8 |

### Main comparison + N07 baselines (TEST split, N03-tuned old / N07-tuned new)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| random | 0.04 [0.03, 0.04] | 0.06 [0.05, 0.07] | 0.12 [0.11, 0.13] | 0.06 [0.05, 0.07] | 0.06 [0.05, 0.07] | 0.06 [0.05, 0.07] | 41.6 [40.1, 43.2] |
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.02 [0.02, 0.02] | 51.3 [50.2, 52.4] |
| episodic | 0.11 [0.10, 0.12] | 0.16 [0.15, 0.17] | 0.25 [0.24, 0.26] | 0.00 [0.00, 0.00] | 0.40 [0.37, 0.42] | 0.02 [0.02, 0.02] | 53.6 [52.8, 54.3] |
| causal_only | 0.60 [0.60, 0.60] | 0.61 [0.61, 0.62] | 0.64 [0.63, 0.64] | 1.00 [1.00, 1.00] | 0.03 [0.03, 0.04] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| graph_ppr | 0.60 [0.60, 0.60] | 0.80 [0.80, 0.80] | 0.80 [0.80, 0.80] | 0.67 [0.67, 0.67] | 1.00 [1.00, 1.00] | 0.04 [0.04, 0.04] | 25.8 [25.8, 25.9] |
| tcmf_mult | 0.40 [0.40, 0.41] | 0.47 [0.46, 0.48] | 0.59 [0.58, 0.60] | 0.60 [0.59, 0.61] | 0.29 [0.27, 0.31] | 0.05 [0.04, 0.05] | 25.7 [25.4, 26.1] |
| tcmf_add | 0.60 [0.60, 0.60] | 0.68 [0.68, 0.69] | 0.80 [0.79, 0.81] | 1.00 [1.00, 1.00] | 0.21 [0.19, 0.23] | 0.33 [0.33, 0.33] | 3.0 [3.0, 3.0] |
| tcmf_shipped | 0.52 [0.51, 0.52] | 0.61 [0.60, 0.62] | 0.74 [0.73, 0.76] | 0.87 [0.86, 0.88] | 0.23 [0.22, 0.25] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.0] |
| tcmf_rrf | 0.34 [0.34, 0.35] | 0.54 [0.53, 0.55] | 0.77 [0.76, 0.78] | 0.72 [0.71, 0.73] | 0.26 [0.24, 0.28] | 0.16 [0.16, 0.16] | 6.3 [6.2, 6.4] |
| mmr | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.03 [0.03, 0.03] | 37.1 [36.5, 37.7] |
| bm25 | 0.41 [0.41, 0.41] | 0.43 [0.42, 0.43] | 0.47 [0.46, 0.47] | 0.05 [0.04, 0.05] | 1.00 [1.00, 1.00] | 0.05 [0.04, 0.05] | 40.7 [39.2, 42.3] |
| summary_buffer | 0.01 [0.01, 0.01] | 0.02 [0.02, 0.02] | 0.14 [0.13, 0.15] | 0.01 [0.00, 0.01] | 0.04 [0.03, 0.05] | 0.02 [0.02, 0.02] | 58.6 [57.7, 59.5] |
| community_summary | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [0.99, 1.00] | 0.02 [0.02, 0.02] | 51.7 [50.5, 52.8] |
| extract_consolidate | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.02 [0.02, 0.02] | 51.1 [50.0, 52.3] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 39 contrasts)

Positive diff = tcmf_add higher (better for recall, worse for root_rank - lower root_rank is better). p_holm <= 0.05 is significant after correction.

| baseline | metric | mean diff | p (raw) | p (holm) |
|---|---|---|---|---|
| random | recall@5 | +0.623 | 0.0000 | 0.0000 |
| random | recall@10 | +0.675 | 0.0000 | 0.0000 |
| random | root_rank | -38.630 | 0.0000 | 0.0000 |
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
| mmr | recall@5 | +0.284 | 0.0000 | 0.0000 |
| mmr | recall@10 | +0.398 | 0.0000 | 0.0000 |
| mmr | root_rank | -34.067 | 0.0000 | 0.0000 |
| bm25 | recall@5 | +0.256 | 0.0000 | 0.0000 |
| bm25 | recall@10 | +0.332 | 0.0000 | 0.0000 |
| bm25 | root_rank | -37.712 | 0.0000 | 0.0000 |
| summary_buffer | recall@5 | +0.663 | 0.0000 | 0.0000 |
| summary_buffer | recall@10 | +0.654 | 0.0000 | 0.0000 |
| summary_buffer | root_rank | -55.569 | 0.0000 | 0.0000 |
| community_summary | recall@5 | +0.285 | 0.0000 | 0.0000 |
| community_summary | recall@10 | +0.399 | 0.0000 | 0.0000 |
| community_summary | root_rank | -48.670 | 0.0000 | 0.0000 |
| extract_consolidate | recall@5 | +0.284 | 0.0000 | 0.0000 |
| extract_consolidate | recall@10 | +0.398 | 0.0000 | 0.0000 |
| extract_consolidate | root_rank | -48.137 | 0.0000 | 0.0000 |

### N07 verify (mixed regime): does each new baseline beat `random` on at least one metric?

- `mmr` beats random on: recall@3, recall@5, recall@10, semantic@5, root_rank
- `bm25` beats random on: recall@3, recall@5, recall@10, semantic@5, root_rank
- `summary_buffer` beats random on: recall@10
- `community_summary` beats random on: recall@3, recall@5, recall@10, semantic@5
- `extract_consolidate` beats random on: recall@3, recall@5, recall@10, semantic@5
