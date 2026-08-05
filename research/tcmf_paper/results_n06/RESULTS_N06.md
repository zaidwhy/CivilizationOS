# TCMF Benchmark: N06 - per-domain tuned real-text tier

Encoder: nomic-embed-text | decision model: qwen2.5:3b-instruct | tune/test = 10/15 per domain | threshold grid: [0.45, 0.55, 0.6, 0.65, 0.75]

**4/8 domains replicate the qualitative story (additive >> multiplicative; decision accuracy tracks causal recall), reported per-domain above - see each domain's verdict line.**

Reported strictly per domain, never pooled. Threshold selected on TUNE by mean tcmf_add recall@5; TEST split never inspected while selecting.

## plague

### Main comparison (threshold=0.55)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.33±0.09 | 0.44±0.08 | 0.61±0.05 | 0.07±0.13 | 1.00±0.00 | 0.08±0.01 | 13.1 |
| episodic | 0.03±0.07 | 0.12±0.10 | 0.71±0.14 | 0.00±0.00 | 0.30±0.24 | 0.08±0.01 | 12.5 |
| causal_only | 0.60±0.00 | 0.77±0.07 | 0.92±0.10 | 1.00±0.00 | 0.43±0.17 | 0.28±0.04 | 3.7 |
| graph_ppr | 0.45±0.09 | 0.61±0.11 | 0.97±0.07 | 0.84±0.17 | 0.27±0.25 | 0.18±0.04 | 5.7 |
| tcmf_mult | 0.32±0.14 | 0.37±0.14 | 0.84±0.08 | 0.38±0.17 | 0.37±0.22 | 0.09±0.01 | 11.5 |
| tcmf_add | 0.60±0.00 | 0.73±0.09 | 1.00±0.00 | 1.00±0.00 | 0.33±0.24 | 0.27±0.05 | 3.8 |
| tcmf_shipped | 0.59±0.05 | 0.69±0.12 | 1.00±0.00 | 0.93±0.13 | 0.33±0.24 | 0.69±0.26 | 1.7 |
| tcmf_rrf | 0.27±0.12 | 0.51±0.10 | 0.97±0.07 | 0.58±0.15 | 0.40±0.20 | 0.13±0.02 | 8.0 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.07 | 0.00 |
| episodic | 0.00 | 0.00 |
| causal_only | 1.00 | 0.60 |
| graph_ppr | 0.84 | 0.33 |
| tcmf_mult | 0.38 | 0.00 |
| tcmf_add | 1.00 | 0.53 |
| tcmf_shipped | 0.93 | 0.67 |
| tcmf_rrf | 0.58 | 0.20 |
| no_retrieval | - | 0.00 |
| oracle | - | 0.73 |

**plague: story REPLICATES.** floor=0.00 ceiling=0.73 additive_recall@10=1.00 multiplicative_recall@10=0.84.

## water

### Main comparison (threshold=0.55)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.28±0.12 | 0.36±0.13 | 0.81±0.09 | 0.07±0.13 | 0.80±0.24 | 0.09±0.01 | 11.7 |
| episodic | 0.00±0.00 | 0.09±0.12 | 0.65±0.15 | 0.00±0.00 | 0.23±0.31 | 0.08±0.01 | 13.2 |
| causal_only | 0.60±0.00 | 0.80±0.15 | 0.92±0.12 | 1.00±0.00 | 0.50±0.37 | 0.32±0.03 | 3.1 |
| graph_ppr | 0.44±0.08 | 0.64±0.13 | 0.91±0.10 | 0.73±0.13 | 0.50±0.32 | 0.16±0.03 | 6.5 |
| tcmf_mult | 0.37±0.14 | 0.40±0.13 | 0.88±0.10 | 0.38±0.21 | 0.43±0.36 | 0.09±0.01 | 10.9 |
| tcmf_add | 0.60±0.00 | 0.77±0.14 | 1.00±0.00 | 1.00±0.00 | 0.43±0.36 | 0.28±0.04 | 3.6 |
| tcmf_shipped | 0.60±0.00 | 0.77±0.14 | 1.00±0.00 | 1.00±0.00 | 0.43±0.36 | 0.76±0.30 | 1.7 |
| tcmf_rrf | 0.29±0.10 | 0.55±0.14 | 0.91±0.10 | 0.58±0.15 | 0.50±0.37 | 0.14±0.02 | 7.5 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.07 | 0.07 |
| episodic | 0.00 | 0.07 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 0.73 | 0.33 |
| tcmf_mult | 0.38 | 0.07 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 1.00 | 0.93 |
| tcmf_rrf | 0.58 | 0.07 |
| no_retrieval | - | 0.00 |
| oracle | - | 0.93 |

**water: story REPLICATES.** floor=0.00 ceiling=0.93 additive_recall@10=1.00 multiplicative_recall@10=0.88.

## cyber

### Main comparison (threshold=0.6)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.20±0.19 | 0.29±0.20 | 0.84±0.17 | 0.16±0.21 | 0.50±0.48 | 0.15±0.07 | 8.0 |
| episodic | 0.00±0.00 | 0.04±0.08 | 0.71±0.14 | 0.00±0.00 | 0.10±0.20 | 0.09±0.01 | 11.9 |
| causal_only | 0.60±0.00 | 0.73±0.12 | 0.83±0.10 | 1.00±0.00 | 0.33±0.30 | 0.33±0.00 | 3.0 |
| graph_ppr | 0.56±0.08 | 0.76±0.15 | 1.00±0.00 | 0.87±0.16 | 0.60±0.20 | 0.21±0.04 | 5.0 |
| tcmf_mult | 0.17±0.10 | 0.20±0.10 | 0.87±0.12 | 0.29±0.17 | 0.07±0.17 | 0.10±0.01 | 10.7 |
| tcmf_add | 0.60±0.00 | 0.60±0.00 | 0.99±0.05 | 1.00±0.00 | 0.00±0.00 | 0.33±0.00 | 3.0 |
| tcmf_shipped | 0.53±0.09 | 0.56±0.08 | 0.99±0.05 | 0.93±0.13 | 0.00±0.00 | 1.00±0.00 | 1.0 |
| tcmf_rrf | 0.29±0.10 | 0.47±0.09 | 0.83±0.12 | 0.67±0.17 | 0.17±0.24 | 0.16±0.03 | 6.7 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.16 | 0.27 |
| episodic | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 0.87 | 0.80 |
| tcmf_mult | 0.29 | 0.20 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 0.93 | 1.00 |
| tcmf_rrf | 0.67 | 0.40 |
| no_retrieval | - | 0.00 |
| oracle | - | 0.87 |

**cyber: story DOES NOT fully replicate.** floor=0.00 ceiling=0.87 additive_recall@10=0.99 multiplicative_recall@10=0.87.

## crime

### Main comparison (threshold=0.55)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.36±0.11 | 0.43±0.07 | 0.79±0.05 | 0.16±0.21 | 0.83±0.24 | 0.29±0.24 | 5.3 |
| episodic | 0.00±0.00 | 0.01±0.05 | 0.69±0.14 | 0.00±0.00 | 0.03±0.12 | 0.09±0.01 | 11.3 |
| causal_only | 0.49±0.10 | 0.65±0.09 | 0.79±0.15 | 1.00±0.00 | 0.13±0.22 | 0.50±0.00 | 2.0 |
| graph_ppr | 0.60±0.00 | 0.60±0.00 | 0.87±0.14 | 1.00±0.00 | 0.00±0.00 | 0.33±0.00 | 3.0 |
| tcmf_mult | 0.24±0.11 | 0.29±0.12 | 0.89±0.12 | 0.47±0.20 | 0.03±0.12 | 0.21±0.16 | 7.7 |
| tcmf_add | 0.53±0.09 | 0.60±0.00 | 0.85±0.15 | 1.00±0.00 | 0.00±0.00 | 0.44±0.09 | 2.4 |
| tcmf_shipped | 0.53±0.09 | 0.57±0.07 | 0.96±0.08 | 0.96±0.11 | 0.00±0.00 | 1.00±0.00 | 1.0 |
| tcmf_rrf | 0.27±0.09 | 0.45±0.11 | 0.81±0.05 | 0.69±0.19 | 0.10±0.20 | 0.26±0.09 | 4.5 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.16 | 1.00 |
| episodic | 0.00 | 1.00 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 1.00 | 1.00 |
| tcmf_mult | 0.47 | 1.00 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 0.96 | 1.00 |
| tcmf_rrf | 0.69 | 1.00 |
| no_retrieval | - | 1.00 |
| oracle | - | 1.00 |

**crime: story DOES NOT fully replicate.** floor=1.00 ceiling=1.00 additive_recall@10=0.85 multiplicative_recall@10=0.89.

## housing

### Main comparison (threshold=0.55)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.25±0.19 | 0.49±0.10 | 0.76±0.08 | 0.16±0.17 | 1.00±0.00 | 0.08±0.01 | 12.7 |
| episodic | 0.00±0.00 | 0.08±0.10 | 0.68±0.10 | 0.00±0.00 | 0.20±0.24 | 0.08±0.01 | 12.8 |
| causal_only | 0.60±0.00 | 0.69±0.12 | 0.80±0.13 | 1.00±0.00 | 0.23±0.31 | 0.33±0.02 | 3.1 |
| graph_ppr | 0.41±0.05 | 0.63±0.20 | 1.00±0.00 | 0.80±0.16 | 0.37±0.34 | 0.18±0.05 | 5.9 |
| tcmf_mult | 0.24±0.08 | 0.27±0.09 | 0.84±0.08 | 0.40±0.13 | 0.07±0.17 | 0.09±0.01 | 11.5 |
| tcmf_add | 0.59±0.05 | 0.60±0.00 | 1.00±0.00 | 0.98±0.08 | 0.03±0.12 | 0.32±0.05 | 3.3 |
| tcmf_shipped | 0.60±0.00 | 0.61±0.05 | 1.00±0.00 | 1.00±0.00 | 0.03±0.12 | 0.90±0.20 | 1.2 |
| tcmf_rrf | 0.28±0.10 | 0.45±0.09 | 0.83±0.14 | 0.62±0.17 | 0.20±0.31 | 0.14±0.03 | 7.4 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.16 | 0.73 |
| episodic | 0.00 | 0.33 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 0.80 | 1.00 |
| tcmf_mult | 0.40 | 1.00 |
| tcmf_add | 0.98 | 1.00 |
| tcmf_shipped | 1.00 | 1.00 |
| tcmf_rrf | 0.62 | 1.00 |
| no_retrieval | - | 0.73 |
| oracle | - | 1.00 |

**housing: story DOES NOT fully replicate.** floor=0.73 ceiling=1.00 additive_recall@10=1.00 multiplicative_recall@10=0.84.

## power

### Main comparison (threshold=0.55)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.31±0.10 | 0.41±0.09 | 0.85±0.15 | 0.09±0.15 | 0.90±0.20 | 0.10±0.02 | 10.3 |
| episodic | 0.03±0.07 | 0.07±0.09 | 0.73±0.12 | 0.00±0.00 | 0.17±0.24 | 0.09±0.01 | 11.9 |
| causal_only | 0.60±0.00 | 0.99±0.05 | 0.99±0.05 | 1.00±0.00 | 0.97±0.12 | 0.29±0.04 | 3.5 |
| graph_ppr | 0.60±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 1.00±0.00 | 0.23±0.02 | 4.5 |
| tcmf_mult | 0.56±0.08 | 0.61±0.09 | 0.99±0.05 | 0.38±0.17 | 0.97±0.12 | 0.11±0.04 | 9.5 |
| tcmf_add | 0.60±0.00 | 0.97±0.07 | 1.00±0.00 | 1.00±0.00 | 0.93±0.17 | 0.25±0.02 | 4.0 |
| tcmf_shipped | 0.60±0.00 | 0.97±0.07 | 1.00±0.00 | 1.00±0.00 | 0.93±0.17 | 1.00±0.00 | 1.0 |
| tcmf_rrf | 0.43±0.10 | 0.57±0.07 | 1.00±0.00 | 0.36±0.08 | 0.90±0.20 | 0.14±0.04 | 7.3 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.09 | 0.13 |
| episodic | 0.00 | 0.00 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 1.00 | 1.00 |
| tcmf_mult | 0.38 | 0.73 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 1.00 | 1.00 |
| tcmf_rrf | 0.36 | 0.73 |
| no_retrieval | - | 0.07 |
| oracle | - | 1.00 |

**power: story REPLICATES.** floor=0.07 ceiling=1.00 additive_recall@10=1.00 multiplicative_recall@10=0.99.

## software-debugging

### Main comparison (threshold=0.6)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.29±0.12 | 0.47±0.14 | 0.92±0.10 | 0.13±0.20 | 0.97±0.12 | 0.10±0.01 | 10.5 |
| episodic | 0.03±0.07 | 0.12±0.10 | 0.75±0.09 | 0.00±0.00 | 0.30±0.24 | 0.08±0.01 | 12.9 |
| causal_only | 0.60±0.00 | 0.80±0.00 | 0.88±0.10 | 1.00±0.00 | 0.50±0.00 | 0.33±0.00 | 3.0 |
| graph_ppr | 0.60±0.00 | 0.80±0.07 | 1.00±0.00 | 0.67±0.12 | 1.00±0.00 | 0.23±0.03 | 4.4 |
| tcmf_mult | 0.36±0.11 | 0.45±0.14 | 0.89±0.12 | 0.44±0.16 | 0.47±0.22 | 0.09±0.01 | 10.8 |
| tcmf_add | 0.60±0.00 | 0.80±0.00 | 1.00±0.00 | 1.00±0.00 | 0.50±0.00 | 0.33±0.00 | 3.0 |
| tcmf_shipped | 0.60±0.00 | 0.80±0.00 | 1.00±0.00 | 1.00±0.00 | 0.50±0.00 | 0.44±0.08 | 2.3 |
| tcmf_rrf | 0.41±0.15 | 0.57±0.07 | 0.93±0.09 | 0.64±0.08 | 0.47±0.12 | 0.13±0.02 | 7.6 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.13 | 1.00 |
| episodic | 0.00 | 1.00 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 0.67 | 1.00 |
| tcmf_mult | 0.44 | 1.00 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 1.00 | 1.00 |
| tcmf_rrf | 0.64 | 1.00 |
| no_retrieval | - | 0.93 |
| oracle | - | 1.00 |

**software-debugging: story DOES NOT fully replicate.** floor=0.93 ceiling=1.00 additive_recall@10=1.00 multiplicative_recall@10=0.89.

## cybersecurity

### Main comparison (threshold=0.6)

| method | recall@3 | recall@5 | recall@10 | causal@5 | semantic@5 | root_mrr | root_rank |
|---|---|---|---|---|---|---|---|
| semantic_rag | 0.24±0.18 | 0.33±0.25 | 0.91±0.12 | 0.22±0.16 | 0.50±0.41 | 0.11±0.01 | 9.4 |
| episodic | 0.01±0.05 | 0.05±0.09 | 0.68±0.12 | 0.00±0.00 | 0.13±0.22 | 0.08±0.01 | 12.3 |
| causal_only | 0.60±0.00 | 0.67±0.09 | 0.81±0.11 | 1.00±0.00 | 0.17±0.24 | 0.33±0.00 | 3.0 |
| graph_ppr | 0.48±0.14 | 0.60±0.16 | 1.00±0.00 | 0.64±0.08 | 0.53±0.34 | 0.10±0.00 | 10.0 |
| tcmf_mult | 0.20±0.07 | 0.23±0.07 | 0.85±0.11 | 0.36±0.08 | 0.03±0.12 | 0.09±0.01 | 11.0 |
| tcmf_add | 0.57±0.07 | 0.60±0.00 | 1.00±0.00 | 1.00±0.00 | 0.00±0.00 | 0.32±0.03 | 3.1 |
| tcmf_shipped | 0.53±0.09 | 0.56±0.08 | 1.00±0.00 | 0.93±0.13 | 0.00±0.00 | 0.93±0.17 | 1.1 |
| tcmf_rrf | 0.21±0.05 | 0.45±0.11 | 0.83±0.10 | 0.71±0.17 | 0.07±0.17 | 0.16±0.02 | 6.5 |

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.22 | 0.80 |
| episodic | 0.00 | 0.60 |
| causal_only | 1.00 | 1.00 |
| graph_ppr | 0.64 | 0.93 |
| tcmf_mult | 0.36 | 0.87 |
| tcmf_add | 1.00 | 1.00 |
| tcmf_shipped | 0.93 | 1.00 |
| tcmf_rrf | 0.71 | 1.00 |
| no_retrieval | - | 0.73 |
| oracle | - | 1.00 |

**cybersecurity: story REPLICATES.** floor=0.73 ceiling=1.00 additive_recall@10=1.00 multiplicative_recall@10=0.85.
