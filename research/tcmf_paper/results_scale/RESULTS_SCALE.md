# TCMF Benchmark: Scale Stress Test (N16, also feeds N13's latency item)

Pure regime, 30 scenarios/point (recall), 15 scenarios/point (latency, median of one timed call each), seed=0. chain_len fixed at 4 throughout - graph size never changes, only the memory pool does.

| pool | tcmf_add causal@5 | graph_ppr causal@5 | margin | BFS-only (ms) | semantic (ms) | fusion (ms) |
|---|---|---|---|---|---|---|
| 17 | 1.000 [1.000,1.000] | 0.333 [0.333,0.333] | +0.667 | 0.004 | 0.138 | 0.493 |
| 78 | 1.000 [1.000,1.000] | 0.333 [0.333,0.333] | +0.667 | 0.005 | 0.591 | 2.050 |
| 378 | 1.000 [1.000,1.000] | 0.333 [0.333,0.333] | +0.667 | 0.006 | 2.993 | 10.190 |
| 978 | 1.000 [1.000,1.000] | 0.333 [0.333,0.333] | +0.667 | 0.010 | 10.441 | 35.209 |
| 1503 | 0.989 [0.967,1.000] | 0.333 [0.333,0.333] | +0.656 | 0.010 | 16.393 | 55.795 |

**Margin closes (causal@5 gap <= 0.02) at pool size:** never, in the tested range
