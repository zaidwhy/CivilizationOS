# TCMF Benchmark: pure regime, N07 additional retrieval baselines

tune seeds: (0, 1) (n=300 each) | test seeds: (2, 3, 4) (n=300 each) | stride: 100000 | pool/scenario: 78 | pre-existing-method hyperparameters: N03-tuned (loaded from results_main_tuned, not re-derived) | new-baseline hyperparameters: swept here on TUNE only, budget=5/operator, selection metric recall@5

New baselines are reimplementable *mechanisms*, not system reimplementations: `mmr` (maximal marginal relevance), `bm25` (lexical, no embeddings), `summary_buffer` (MemGPT-style recent window + paged archival summary), `community_summary` (GraphRAG-style cluster-then-retrieve), `extract_consolidate` (Mem0-style dedupe/merge before ranking). All 5 evaluated on the TEST split only.

### N07 tune-set hyperparameter sweep for the 5 new baselines (recall@5, mean over TUNE split only, budget=5 candidates/operator - same protocol N03 used)

| operator | candidate | tune recall@5 | selected |
|---|---|---|---|
| mmr_lambda | 0.1 | 0.0917 | |
| mmr_lambda | 0.3 | 0.1006 **<-selected** | |
| mmr_lambda | 0.5 | 0.0811 | |
| mmr_lambda | 0.7 | 0.0000 | |
| mmr_lambda | 0.9 | 0.0000 | |
| bm25_k1 | 0.5 | 0.0000 **<-selected** | |
| bm25_k1 | 1.0 | 0.0000 | |
| bm25_k1 | 1.5 | 0.0000 | |
| bm25_k1 | 2.0 | 0.0000 | |
| bm25_k1 | 2.5 | 0.0000 | |
| summary_buffer_window | 5 | 0.0067 **<-selected** | |
| summary_buffer_window | 10 | 0.0067 | |
| summary_buffer_window | 20 | 0.0067 | |
| summary_buffer_window | 40 | 0.0067 | |
| summary_buffer_window | 60 | 0.0067 | |
| community_n | 2 | 0.0000 **<-selected** | |
| community_n | 4 | 0.0000 | |
| community_n | 6 | 0.0000 | |
| community_n | 8 | 0.0000 | |
| community_n | 12 | 0.0000 | |
| consolidate_threshold | 0.8 | 0.0000 **<-selected** | |
| consolidate_threshold | 0.85 | 0.0000 | |
| consolidate_threshold | 0.9 | 0.0000 | |
| consolidate_threshold | 0.95 | 0.0000 | |
| consolidate_threshold | 0.98 | 0.0000 | |

| operator | selected value |
|---|---|
| mmr_lambda | 0.3 |
| bm25_k1 | 0.5 |
| summary_buffer_window | 5 |
| community_n | 2 |
| consolidate_threshold | 0.8 |

### Main comparison + N07 baselines (TEST split, N03-tuned old / N07-tuned new)

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
| mmr | 0.00 [0.00, 0.00] | 0.05 [0.04, 0.05] | 0.10 [0.09, 0.11] | 0.28 [0.26, 0.30] | 0.10 [0.09, 0.10] | 14.6 [14.2, 15.0] | 0.14 [0.13, 0.14] |
| bm25 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.01 [0.01, 0.01] | 78.0 [78.0, 78.0] | 0.00 [0.00, 0.00] |
| summary_buffer | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.01] | 0.01 [0.00, 0.01] | 0.02 [0.02, 0.03] | 0.02 [0.02, 0.02] | 56.1 [55.2, 57.0] | 0.01 [0.01, 0.01] |
| community_summary | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.02 [0.02, 0.02] | 50.4 [49.2, 51.5] | 0.00 [0.00, 0.00] |
| extract_consolidate | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.02 [0.02, 0.02] | 50.0 [48.9, 51.2] | 0.00 [0.00, 0.00] |

### Significance: tcmf_add vs every baseline (paired Wilcoxon signed-rank, Holm-Bonferroni corrected across all 28 contrasts)

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
| mmr | recall@5 | +0.899 | 0.0000 | 0.0000 |
| mmr | root_rank | -11.581 | 0.0000 | 0.0000 |
| bm25 | recall@5 | +1.000 | 0.0000 | 0.0000 |
| bm25 | root_rank | -74.990 | 0.0000 | 0.0000 |
| summary_buffer | recall@5 | +0.993 | 0.0000 | 0.0000 |
| summary_buffer | root_rank | -53.113 | 0.0000 | 0.0000 |
| community_summary | recall@5 | +1.000 | 0.0000 | 0.0000 |
| community_summary | root_rank | -47.344 | 0.0000 | 0.0000 |
| extract_consolidate | recall@5 | +1.000 | 0.0000 | 0.0000 |
| extract_consolidate | root_rank | -47.033 | 0.0000 | 0.0000 |

### N07 verify (pure regime): does each new baseline beat `random` on at least one metric?

- `mmr` beats random on: recall@3, recall@5, recall@10, root_mrr, root_rank, ndcg@10
- `bm25` beats random on NO metric - see NIGHT_LOG.md for the mechanistic investigation of why (bug vs. real benchmark property)
- `summary_buffer` beats random on NO metric - see NIGHT_LOG.md for the mechanistic investigation of why (bug vs. real benchmark property)
- `community_summary` beats random on NO metric - see NIGHT_LOG.md for the mechanistic investigation of why (bug vs. real benchmark property)
- `extract_consolidate` beats random on NO metric - see NIGHT_LOG.md for the mechanistic investigation of why (bug vs. real benchmark property)
