# TCMF Benchmark: Second Encoder Comparison (N13)

n=120 (tune=40, test=80), seed=0, identical real-text domains and scenario seeds for both encoders - the only thing that changes is which encoder produced the embeddings.

| encoder | dim | anisotropy (unrelated cosine) | selected tau | recall@5 order (TEST, descending) |
|---|---|---|---|---|
| nomic-embed-text | 768 | 0.447 | 0.6 | graph_ppr > causal_only > tcmf_add > tcmf_shipped > tcmf_rrf > semantic_rag > tcmf_mult > episodic |
| all-MiniLM-L6-v2 | 384 | 0.123 | 0.3 | causal_only > graph_ppr > tcmf_add > tcmf_shipped > tcmf_rrf > semantic_rag > tcmf_mult > episodic |

**Method ordering preserved across encoders:** False

### nomic-embed-text

### nomic-embed-text: TEST split (threshold=0.6)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.28±0.15 | 0.39±0.17 | 0.81±0.14 | 0.13±0.19 | 0.78±0.33 | 0.11±0.06 | 10.4 |
| episodic | 0.01±0.05 | 0.07±0.10 | 0.70±0.12 | 0.00±0.04 | 0.17±0.24 | 0.08±0.01 | 12.5 |
| causal_only | 0.60±0.00 | 0.71±0.11 | 0.84±0.13 | 1.00±0.00 | 0.29±0.28 | 0.32±0.03 | 3.2 |
| graph_ppr | 0.50±0.11 | 0.72±0.20 | 0.97±0.08 | 0.79±0.17 | 0.61±0.39 | 0.20±0.07 | 5.8 |
| tcmf_mult | 0.25±0.15 | 0.32±0.14 | 0.85±0.10 | 0.37±0.17 | 0.25±0.25 | 0.09±0.01 | 11.2 |
| tcmf_add | 0.59±0.05 | 0.67±0.11 | 1.00±0.00 | 0.99±0.06 | 0.18±0.24 | 0.31±0.04 | 3.3 |
| tcmf_shipped | 0.56±0.08 | 0.64±0.14 | 1.00±0.00 | 0.94±0.13 | 0.18±0.24 | 0.87±0.22 | 1.3 |
| tcmf_rrf | 0.28±0.11 | 0.48±0.13 | 0.87±0.11 | 0.62±0.16 | 0.28±0.26 | 0.14±0.03 | 7.4 |

### all-MiniLM-L6-v2

### all-MiniLM-L6-v2: TEST split (threshold=0.3)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.29±0.19 | 0.39±0.23 | 0.87±0.14 | 0.24±0.25 | 0.61±0.40 | 0.23±0.30 | 8.6 |
| episodic | 0.05±0.08 | 0.10±0.10 | 0.74±0.11 | 0.01±0.06 | 0.22±0.26 | 0.08±0.01 | 12.0 |
| causal_only | 0.53±0.10 | 0.72±0.16 | 0.87±0.11 | 0.94±0.15 | 0.38±0.33 | 0.26±0.07 | 4.2 |
| graph_ppr | 0.53±0.12 | 0.71±0.23 | 0.97±0.07 | 0.81±0.23 | 0.57±0.37 | 0.20±0.09 | 6.2 |
| tcmf_mult | 0.25±0.17 | 0.30±0.19 | 0.86±0.10 | 0.26±0.20 | 0.38±0.33 | 0.09±0.02 | 10.9 |
| tcmf_add | 0.49±0.14 | 0.65±0.19 | 0.99±0.04 | 0.83±0.21 | 0.39±0.32 | 0.21±0.08 | 5.5 |
| tcmf_shipped | 0.42±0.18 | 0.60±0.19 | 0.99±0.04 | 0.77±0.26 | 0.35±0.29 | 0.69±0.36 | 2.3 |
| tcmf_rrf | 0.29±0.13 | 0.48±0.15 | 0.90±0.10 | 0.54±0.19 | 0.39±0.32 | 0.13±0.03 | 8.1 |
