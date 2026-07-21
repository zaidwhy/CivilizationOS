# TCMF Benchmark Results

Scenarios: 300 | seed: 0 | dim: 64 | chain_len: 4 | distractors: 6 | noise: 8 | alpha_mem: 0.9 | gold/scenario: 3

Mean±std over scenarios. `root_rank` = mean rank of the root-cause memory (lower better). The mechanism under test is the real `api.memory.tcmf.TCMFRetriever`; baselines and fusion variants share identical episodic scores and causal boosts.

### Main comparison

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| random | 0.06±0.13 | 0.17±0.21 | 0.29±0.24 | 0.58±0.25 | 0.22±0.25 | 8.9 | 0.34±0.20 |
| recency | 0.01±0.04 | 0.03±0.09 | 0.04±0.11 | 0.26±0.24 | 0.07±0.01 | 15.3 | 0.09±0.09 |
| semantic_rag | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.34±0.25 | 0.09±0.03 | 11.7 | 0.14±0.11 |
| episodic | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.47±0.27 | 0.08±0.02 | 13.0 | 0.15±0.10 |
| causal_only | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| graph_ppr | 0.33±0.00 | 0.33±0.00 | 0.33±0.02 | 1.00±0.03 | 0.11±0.00 | 9.1 | 0.61±0.02 |
| tcmf_mult | 0.01±0.05 | 0.01±0.06 | 0.02±0.08 | 0.75±0.18 | 0.09±0.02 | 11.6 | 0.26±0.10 |
| tcmf_add | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| tcmf_shipped | 0.33±0.00 | 0.73±0.13 | 0.76±0.15 | 1.00±0.00 | 1.00±0.00 | 1.0 | 0.95±0.02 |
| tcmf_rrf | 0.14±0.16 | 0.42±0.16 | 0.66±0.17 | 1.00±0.00 | 0.15±0.04 | 7.0 | 0.60±0.08 |

### Ablation: fusion operator (F3/F4)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| mult (old, l=0.6) | 0.01±0.05 | 0.01±0.06 | 0.02±0.08 | 0.75±0.18 | 0.09±0.02 | 11.6 | 0.26±0.10 |
| mult (old, l=8) | 0.33±0.00 | 0.96±0.11 | 0.97±0.10 | 1.00±0.00 | 0.31±0.06 | 3.5 | 0.83±0.04 |
| additive (l=4) | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| rrf | 0.14±0.16 | 0.42±0.16 | 0.66±0.17 | 1.00±0.00 | 0.15±0.04 | 7.0 | 0.60±0.08 |
| shipped retriever | 0.33±0.00 | 0.73±0.13 | 0.76±0.15 | 1.00±0.00 | 1.00±0.00 | 1.0 | 0.95±0.02 |

### Ablation: additive causal weight lambda

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| additive l=0.5 | 0.01±0.05 | 0.01±0.06 | 0.02±0.08 | 0.82±0.17 | 0.09±0.01 | 10.9 | 0.30±0.10 |
| additive l=1 | 0.31±0.08 | 0.34±0.09 | 0.36±0.11 | 0.98±0.09 | 0.11±0.01 | 9.3 | 0.60±0.07 |
| additive l=2 | 0.33±0.00 | 0.67±0.02 | 0.67±0.04 | 1.00±0.00 | 0.11±0.02 | 8.9 | 0.71±0.01 |
| additive l=4 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| additive l=8 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |

### Ablation: causal_sim_threshold

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| threshold=0.3 | 0.33±0.00 | 0.97±0.10 | 1.00±0.03 | 1.00±0.00 | 0.32±0.03 | 3.1 | 0.84±0.02 |
| threshold=0.45 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| threshold=0.6 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| threshold=0.75 | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |

### Ablation: depth-weighting direction (F5)

| method | recall@1 | recall@3 | recall@5 | recall@10 | root_mrr | root_rank | ndcg@10 |
|---|---|---|---|---|---|---|---|
| favor proximate (shipped) | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.33±0.00 | 3.0 | 0.84±0.00 |
| favor root (fix) | 0.33±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 1.0 | 1.00±0.00 |

### Ablation: difficulty vs recall@5 (lower alpha = noisier embeddings)

| method | alpha=0.75 | alpha=0.8 | alpha=0.85 | alpha=0.9 | alpha=0.95 |
|---|---|---|---|---|---|
| semantic_rag | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| tcmf_mult | 0.04 | 0.04 | 0.03 | 0.02 | 0.01 |
| tcmf_add | 0.98 | 0.99 | 1.00 | 1.00 | 1.00 |
