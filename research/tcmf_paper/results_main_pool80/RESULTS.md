# TCMF Benchmark Results

Scenarios: 300 per seed | seeds: [0, 1, 2, 3, 4] (5x300 = 1500 total) | dim: 64 | chain_len: 4 | distractors: 20 | noise: 55 | pool size: 78 | alpha_mem: 0.9 | gold/scenario: 3

Mean±std over scenarios (main comparison pools scenarios across all seeds before computing mean/std; remaining ablations use seed[0] only). `root_rank` = mean rank of the root-cause memory (lower better). The mechanism under test is the real `api.memory.tcmf.TCMFRetriever`; baselines and fusion variants share identical episodic scores and causal boosts.

### Main comparison

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| random | 0.01±0.07 | 0.04±0.12 | 0.08±0.15 | 0.14±0.19 | 0.06±0.10 | 41.5 | 0.08±0.13 |
| recency | 0.00±0.02 | 0.00±0.03 | 0.01±0.05 | 0.01±0.06 | 0.02±0.00 | 65.8 | 0.00±0.03 |
| semantic_rag | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.02±0.01 | 47.8 | 0.00±0.00 |
| episodic | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.02±0.01 | 51.2 | 0.00±0.00 |
| causal_only | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| graph_ppr | 0.33±0.00 | 0.33±0.00 | 0.33±0.00 | 0.33±0.02 | 0.04±0.00 | 24.0 | 0.32±0.01 |
| tcmf_mult | 0.00±0.03 | 0.01±0.05 | 0.01±0.05 | 0.01±0.06 | 0.03±0.01 | 41.4 | 0.01±0.04 |
| tcmf_add | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| tcmf_shipped | 0.33±0.00 | 0.74±0.14 | 0.77±0.15 | 0.80±0.16 | 1.00±0.00 | 1.0 | 0.90±0.07 |
| tcmf_rrf | 0.08±0.15 | 0.36±0.18 | 0.56±0.18 | 0.97±0.10 | 0.13±0.03 | 8.1 | 0.53±0.11 |

### Main comparison recall@10, per seed (stability check)

| method | seed=0 | seed=1 | seed=2 | seed=3 | seed=4 | pooled |
|---|---|---|---|---|---|---|
| random | 0.14 | 0.14 | 0.14 | 0.14 | 0.14 | 0.14 |
| recency | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 |
| semantic_rag | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| episodic | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| graph_ppr | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 |
| tcmf_mult | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 |
| tcmf_add | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| tcmf_shipped | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 |
| tcmf_rrf | 0.97 | 0.97 | 0.97 | 0.97 | 0.97 | 0.97 |

### Random-baseline sanity check (analytic vs measured)

pool size = 3 gold + 20 distractors + 55 noise = 78

| k | analytic E[recall@k] = k/pool | measured (random, pooled) |
|---|---|---|
| 1 | 0.013 | 0.014 |
| 3 | 0.038 | 0.043 |
| 5 | 0.064 | 0.077 |
| 10 | 0.128 | 0.139 |

### Ablation: fusion operator (F3/F4)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| mult (old, l=0.6) | 0.00±0.03 | 0.01±0.05 | 0.01±0.05 | 0.01±0.07 | 0.03±0.01 | 41.3 | 0.01±0.04 |
| mult (old, l=8) | 0.33±0.02 | 0.95±0.11 | 0.96±0.11 | 0.97±0.10 | 0.30±0.09 | 4.8 | 0.81±0.10 |
| additive (l=4) | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| rrf | 0.08±0.14 | 0.36±0.18 | 0.56±0.18 | 0.97±0.10 | 0.13±0.03 | 8.1 | 0.53±0.11 |
| shipped retriever | 0.33±0.00 | 0.74±0.14 | 0.77±0.15 | 0.80±0.16 | 1.00±0.00 | 1.0 | 0.90±0.07 |

### Ablation: additive causal weight lambda

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.00±0.04 | 0.01±0.06 | 0.01±0.06 | 0.02±0.08 | 0.03±0.01 | 34.5 | 0.01±0.05 |
| additive l=1 | 0.33±0.05 | 0.35±0.09 | 0.36±0.10 | 0.38±0.12 | 0.04±0.00 | 24.6 | 0.34±0.06 |
| additive l=2 | 0.33±0.00 | 0.67±0.02 | 0.67±0.04 | 0.68±0.06 | 0.05±0.03 | 22.2 | 0.53±0.04 |
| additive l=4 | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| additive l=8 | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |

### Ablation: causal_sim_threshold

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| threshold=0.3 | 0.33±0.00 | 0.89±0.16 | 0.98±0.08 | 1.00±0.03 | 0.30±0.06 | 3.7 | 0.82±0.04 |
| threshold=0.45 | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| threshold=0.6 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| threshold=0.75 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |

### Ablation: depth-weighting direction (F5)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| favor proximate (shipped) | 0.33±0.00 | 0.99±0.04 | 1.00±0.00 | 1.00±0.00 | 0.33±0.01 | 3.0 | 0.84±0.01 |
| favor root (fix) | 0.33±0.00 | 1.00±0.04 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 1.0 | 1.00±0.00 |

### Ablation: difficulty vs recall@5 (lower alpha = noisier embeddings)

| method | alpha=0.75 | alpha=0.8 | alpha=0.85 | alpha=0.9 | alpha=0.95 |
|---|---|---|---|---|---|
| semantic_rag | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| tcmf_mult | 0.04 | 0.04 | 0.03 | 0.02 | 0.01 |
| tcmf_add | 0.98 | 0.99 | 1.00 | 1.00 | 1.00 |
