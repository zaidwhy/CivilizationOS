# TCMF Benchmark: Real-Text Tier (Ollama nomic-embed-text)

Scenarios: 120 | seed: 0 | encoder: nomic-embed-text (768d) | causal threshold: 0.6 | domains: 6

Natural-language scenarios; ground truth by construction, geometry by the encoder. `causal@5`/`semantic@5` = recall over each gold subset.

### Main comparison (real text)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.32±0.13 | 0.43±0.10 | 0.76±0.16 | 0.13±0.18 | 0.88±0.26 | 0.14±0.15 | 10.3 |
| episodic | 0.02±0.06 | 0.08±0.11 | 0.70±0.14 | 0.01±0.06 | 0.17±0.25 | 0.08±0.01 | 12.4 |
| causal_only | 0.60±0.00 | 0.68±0.10 | 0.85±0.13 | 1.00±0.00 | 0.20±0.26 | 0.32±0.03 | 3.2 |
| graph_ppr | 0.53±0.09 | 0.74±0.20 | 0.96±0.11 | 0.90±0.15 | 0.50±0.42 | 0.22±0.07 | 4.9 |
| tcmf_mult | 0.25±0.14 | 0.31±0.14 | 0.87±0.10 | 0.39±0.19 | 0.18±0.26 | 0.09±0.01 | 11.3 |
| tcmf_add | 0.57±0.07 | 0.64±0.08 | 1.00±0.00 | 0.99±0.04 | 0.11±0.21 | 0.30±0.05 | 3.4 |
| tcmf_shipped | 0.54±0.10 | 0.60±0.12 | 1.00±0.00 | 0.92±0.15 | 0.12±0.21 | 0.96±0.13 | 1.1 |
| tcmf_rrf | 0.28±0.11 | 0.46±0.12 | 0.85±0.11 | 0.64±0.19 | 0.19±0.26 | 0.14±0.03 | 7.3 |

### Edge-dropout robustness (real text, overall recall@10)

| method | drop=0.0 | drop=0.5 | drop=1.0 |
|---|---|---|---|
| semantic_rag | 0.76 | 0.76 | 0.76 |
| causal_only | 0.85 | 0.71 | 0.64 |
| tcmf_add | 1.00 | 0.75 | 0.70 |
