# TCMF Benchmark: Multi-Crisis Stress Test (N16)

60 scenarios per n_crises point (seed=0), every crisis in every scenario queried and scored separately - per-crisis metrics, never pooled across crises. `other_crisis_boost` is the causal boost the OTHER crises' true ancestor witnesses receive when querying THIS crisis - the cross-contamination check.

| n_crises | pool | n_queries | causal@5 | recall@5 | own_boost_mean | other_crisis_boost_mean | other_crisis_boost_max |
|---|---|---|---|---|---|---|---|
| 2 | 34 | 120 | 1.000 [1.000,1.000] | 1.000 | 0.569 | 0.0000 | 0.0000 [0.0000,0.0000] |
| 3 | 43 | 180 | 1.000 [1.000,1.000] | 1.000 | 0.569 | 0.0000 | 0.0000 [0.0000,0.0000] |
| 4 | 52 | 240 | 1.000 [1.000,1.000] | 1.000 | 0.570 | 0.0000 | 0.0000 [0.0000,0.0000] |
| 8 | 88 | 480 | 0.999 [0.998,1.000] | 0.999 | 0.571 | 0.0001 | 0.0023 [0.0003,0.0052] |
