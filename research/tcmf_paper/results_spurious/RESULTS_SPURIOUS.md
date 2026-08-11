# TCMF Benchmark: Spurious-Edge Robustness (N04)

Mixed regime, pool = 81 (chain_len 4 -> 3 causal-gold + 1 crisis, 55 noise, 20 distractors, 2 semantic-gold), 5 seeds (stride 100000), n=300 scenarios/seed for the curve, n=100 for the 2-D grid (coarser, per the queue's own 'coarse resolution' instruction). A spurious edge is a single fabricated false-ancestor event, injected with probability p per scenario, aligned to the crisis surface topic (the SAME topic distractors and semantic-gold share) and linked directly into the crisis - independent of `edge_dropout`.

**p=0 reproducibility check:** VERIFIED bit-for-bit against results_mixed_scale\results_mixed.json (max diff 0.00e+00)

### Spurious-rate curve (dropout=0 fixed), recall@10

| method | p=0.0 | p=0.05 | p=0.1 | p=0.2 | p=0.4 |
|---|---|---|---|---|---|
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] |
| causal_only | 0.64 [0.63, 0.64] | 0.64 [0.63, 0.64] | 0.63 [0.63, 0.64] | 0.63 [0.63, 0.64] | 0.63 [0.63, 0.63] |
| graph_ppr | 0.80 [0.80, 0.80] | 0.78 [0.77, 0.78] | 0.76 [0.75, 0.76] | 0.72 [0.71, 0.72] | 0.63 [0.62, 0.64] |
| tcmf_add | 0.80 [0.79, 0.81] | 0.79 [0.78, 0.79] | 0.78 [0.77, 0.78] | 0.76 [0.75, 0.76] | 0.71 [0.71, 0.72] |
| tcmf_shipped | 0.74 [0.74, 0.75] | 0.75 [0.74, 0.75] | 0.75 [0.74, 0.76] | 0.75 [0.74, 0.76] | 0.76 [0.75, 0.76] |

### Precision-side damage: P(a distractor is promoted into the top-5)

| method | p=0.0 | p=0.05 | p=0.1 | p=0.2 | p=0.4 |
|---|---|---|---|---|---|
| semantic_rag | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| causal_only | 0.46 [0.43, 0.48] | 0.48 [0.46, 0.51] | 0.51 [0.48, 0.53] | 0.57 [0.54, 0.59] | 0.68 [0.66, 0.71] |
| graph_ppr | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| tcmf_add | 0.98 [0.97, 0.99] | 0.98 [0.97, 0.99] | 0.98 [0.97, 0.99] | 0.98 [0.97, 0.99] | 0.99 [0.98, 0.99] |
| tcmf_shipped | 0.99 [0.98, 0.99] | 0.99 [0.98, 0.99] | 0.99 [0.98, 0.99] | 0.99 [0.98, 0.99] | 0.99 [0.99, 1.00] |

**Crossover: rate p at which tcmf_add's recall@10 first drops below semantic_rag's:** never, across p in (0.0, 0.05, 0.1, 0.2, 0.4)

### Dropout-only curve (spurious=0 fixed), recall@10 - Fig 5's CI'd complement to F7

| method | drop=0.0 | drop=0.25 | drop=0.5 | drop=0.75 | drop=1.0 |
|---|---|---|---|---|---|
| semantic_rag | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] | 0.40 [0.40, 0.40] |
| causal_only | 0.64 [0.63, 0.64] | 0.43 [0.41, 0.44] | 0.28 [0.27, 0.29] | 0.19 [0.18, 0.20] | 0.13 [0.12, 0.14] |
| graph_ppr | 0.80 [0.80, 0.80] | 0.64 [0.63, 0.65] | 0.52 [0.52, 0.53] | 0.46 [0.45, 0.46] | 0.40 [0.40, 0.40] |
| tcmf_add | 0.80 [0.79, 0.81] | 0.57 [0.56, 0.58] | 0.41 [0.40, 0.42] | 0.31 [0.31, 0.32] | 0.25 [0.24, 0.25] |
| tcmf_shipped | 0.74 [0.74, 0.75] | 0.76 [0.75, 0.76] | 0.77 [0.76, 0.78] | 0.78 [0.78, 0.79] | 0.80 [0.79, 0.81] |

### 2-D grid: recall@10, dropout x spurious rate (coarse resolution)

**semantic_rag**

| dropout \ spurious | p=0.0 | p=0.05 | p=0.1 | p=0.2 | p=0.4 |
|---|---|---|---|---|---|
| drop=0.0 | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| drop=0.2 | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| drop=0.4 | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |

**causal_only**

| dropout \ spurious | p=0.0 | p=0.05 | p=0.1 | p=0.2 | p=0.4 |
|---|---|---|---|---|---|
| drop=0.0 | 0.64 | 0.63 | 0.63 | 0.63 | 0.63 |
| drop=0.2 | 0.46 | 0.46 | 0.46 | 0.48 | 0.51 |
| drop=0.4 | 0.32 | 0.32 | 0.33 | 0.36 | 0.41 |

**tcmf_add**

| dropout \ spurious | p=0.0 | p=0.05 | p=0.1 | p=0.2 | p=0.4 |
|---|---|---|---|---|---|
| drop=0.0 | 0.79 | 0.78 | 0.77 | 0.75 | 0.70 |
| drop=0.2 | 0.60 | 0.59 | 0.59 | 0.59 | 0.58 |
| drop=0.4 | 0.45 | 0.45 | 0.46 | 0.47 | 0.48 |
