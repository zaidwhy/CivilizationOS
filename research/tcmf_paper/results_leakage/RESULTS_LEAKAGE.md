# N26: boost leakage - causal@5 by operator, weight and depth weighting

## False direct-cause edge in a fraction p of mixed-regime scenarios (pool 80, n=1500)

| setting | add_l4_prox | mult_l16_prox | mult_l32_prox | causal_only_prox | add_l4_root | mult_l16_root | mult_l32_root | causal_only_root | mult-only unreachable (prox/root) | both unreachable (prox/root) |
|---|---|---|---|---|---|---|---|---|---|---|
| p=0.0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.001 / 0.001 | 0.009 / 0.000 |
| p=0.1 | 0.926 | 0.890 | 0.890 | 0.927 | 0.963 | 0.952 | 0.957 | 1.000 | 0.001 / 0.001 | 0.118 / 0.000 |
| p=0.25 | 0.825 | 0.741 | 0.741 | 0.827 | 0.913 | 0.886 | 0.896 | 0.999 | 0.001 / 0.003 | 0.267 / 0.000 |
| p=0.5 | 0.646 | 0.478 | 0.478 | 0.650 | 0.826 | 0.765 | 0.786 | 0.999 | 0.001 / 0.004 | 0.529 / 0.000 |
| p=1.0 | 0.324 | 0.005 | 0.006 | 0.333 | 0.668 | 0.548 | 0.594 | 0.997 | 0.000 / 0.007 | 1.000 / 0.000 |

## Real text, six domains (n=120), similarity threshold tau

| setting | add_l4_prox | mult_l16_prox | mult_l32_prox | causal_only_prox | add_l4_root | mult_l16_root | mult_l32_root | causal_only_root | mult-only unreachable (prox/root) | both unreachable (prox/root) |
|---|---|---|---|---|---|---|---|---|---|---|
| tau=0.45 | 0.544 | 0.478 | 0.483 | 0.883 | 0.736 | 0.658 | 0.672 | 0.956 | 0.767 / 0.392 | 0.492 / 0.000 |
| tau=0.5 | 0.828 | 0.781 | 0.789 | 0.900 | 0.917 | 0.853 | 0.864 | 0.967 | 0.117 / 0.208 | 0.492 / 0.000 |
| tau=0.55 | 0.972 | 0.981 | 0.981 | 0.981 | 0.992 | 0.992 | 0.992 | 1.000 | 0.025 / 0.000 | 0.117 / 0.000 |
| tau=0.6 | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 / 0.000 | 0.000 / 0.000 |

Full arm grid (additive lambda 2/4/8/16, multiplicative 0.6/8/16/32, both depth weightings) with recall@5, semantic@5 and root rank is in results_leakage.json.
