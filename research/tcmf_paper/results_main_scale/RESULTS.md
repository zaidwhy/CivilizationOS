# TCMF Benchmark Results

Scenarios: 300 per seed x 5 seed(s) = 1500 total | seeds: [0, 1, 2, 3, 4] (multi-seed, stride 100000) | dim: 64 | chain_len: 4 | distractors: 20 | noise: 55 | pool/scenario: 78 | alpha_mem: 0.9 | gold/scenario: 3

Mean±std over scenarios (pooled across all seeds). `root_rank` = mean rank of the root-cause memory (lower better). The mechanism under test is the real `api.memory.tcmf.TCMFRetriever`; baselines and fusion variants share identical episodic scores and causal boosts.

### Main comparison

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| random | 0.01±0.06 | 0.04±0.11 | 0.07±0.14 | 0.13±0.19 | 0.06±0.12 | 39.2 | 0.08±0.13 |
| recency | 0.00±0.03 | 0.00±0.04 | 0.01±0.05 | 0.02±0.07 | 0.02±0.00 | 65.9 | 0.01±0.04 |
| semantic_rag | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.02±0.01 | 49.7 | 0.00±0.00 |
| episodic | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.02±0.01 | 51.7 | 0.00±0.00 |
| causal_only | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| graph_ppr | 0.33±0.00 | 0.33±0.01 | 0.33±0.01 | 0.33±0.02 | 0.04±0.00 | 24.0 | 0.32±0.01 |
| tcmf_mult | 0.00±0.04 | 0.01±0.05 | 0.01±0.06 | 0.02±0.07 | 0.03±0.01 | 41.6 | 0.01±0.04 |
| tcmf_add | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| tcmf_shipped | 0.33±0.00 | 0.76±0.15 | 0.79±0.16 | 0.82±0.17 | 1.00±0.00 | 1.0 | 0.91±0.07 |
| tcmf_rrf | 0.09±0.15 | 0.35±0.18 | 0.56±0.19 | 0.97±0.10 | 0.13±0.03 | 8.2 | 0.53±0.11 |

### Analytic vs empirical random baseline (N01 sanity check)

| k | analytic k/pool | empirical random recall@k |
|---|---|---|
| 1 | 0.0128 | 0.0129 |
| 3 | 0.0385 | 0.0391 |
| 5 | 0.0641 | 0.0676 |
| 10 | 0.1282 | 0.1338 |

### Seed stability: recall@10 per individual seed (not pooled)

| seed | random | semantic_rag | causal_only | tcmf_add | tcmf_shipped |
|---|---|---|---|---|---|
| 0 | 0.14 | 0.00 | 1.00 | 1.00 | 0.80 |
| 1 | 0.12 | 0.00 | 1.00 | 1.00 | 0.83 |
| 2 | 0.12 | 0.00 | 1.00 | 1.00 | 0.83 |
| 3 | 0.15 | 0.00 | 1.00 | 1.00 | 0.82 |
| 4 | 0.13 | 0.00 | 1.00 | 1.00 | 0.83 |

### Ablation: fusion operator (F3/F4)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| mult (old, l=0.6) | 0.00±0.04 | 0.01±0.05 | 0.01±0.06 | 0.02±0.07 | 0.03±0.01 | 41.6 | 0.01±0.04 |
| mult (old, l=8) | 0.33±0.01 | 0.95±0.12 | 0.96±0.11 | 0.96±0.10 | 0.30±0.09 | 5.0 | 0.80±0.10 |
| additive (l=4) | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| rrf | 0.09±0.15 | 0.35±0.18 | 0.56±0.19 | 0.97±0.10 | 0.13±0.03 | 8.2 | 0.53±0.11 |
| shipped retriever | 0.33±0.00 | 0.76±0.15 | 0.79±0.16 | 0.82±0.17 | 1.00±0.00 | 1.0 | 0.91±0.07 |

### Ablation: additive causal weight lambda

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.00±0.04 | 0.01±0.05 | 0.01±0.06 | 0.02±0.08 | 0.03±0.01 | 34.7 | 0.01±0.05 |
| additive l=1 | 0.33±0.04 | 0.36±0.10 | 0.37±0.10 | 0.38±0.12 | 0.04±0.00 | 24.6 | 0.34±0.06 |
| additive l=2 | 0.33±0.00 | 0.67±0.03 | 0.67±0.04 | 0.68±0.05 | 0.05±0.03 | 22.2 | 0.53±0.04 |
| additive l=4 | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| additive l=8 | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |

### Ablation: causal_sim_threshold

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| threshold=0.3 | 0.33±0.00 | 0.89±0.16 | 0.97±0.10 | 1.00±0.04 | 0.29±0.07 | 3.8 | 0.82±0.05 |
| threshold=0.45 | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| threshold=0.6 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| threshold=0.75 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |

### Ablation: depth-weighting direction (F5)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| favor proximate (shipped) | 0.33±0.00 | 1.00±0.03 | 1.00±0.01 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| favor root (fix) | 0.33±0.00 | 1.00±0.04 | 1.00±0.01 | 1.00±0.00 | 1.00±0.00 | 1.0 | 1.00±0.00 |

### Ablation: difficulty vs recall@5 (lower alpha = noisier embeddings)

| method | alpha=0.75 | alpha=0.8 | alpha=0.85 | alpha=0.9 | alpha=0.95 |
|---|---|---|---|---|---|
| semantic_rag | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| tcmf_mult | 0.02 | 0.02 | 0.01 | 0.01 | 0.01 |
| tcmf_add | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
