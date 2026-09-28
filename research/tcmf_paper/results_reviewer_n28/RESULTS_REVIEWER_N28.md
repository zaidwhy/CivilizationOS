# N28: reviewer-requested checks

## A. Operator isolation under leakage (recall@5; multiplicative = best over a dense lambda grid 0.25-512, oracle-chosen on test)

| setting | add (norm, lam=4) | best mult (norm) [lam] | mult norm limit | best mult (raw) [lam] | mult raw limit |
|---|---|---|---|---|---|
| spurious_p0.0_prox | 0.679 | 0.679 [128] | 0.679 | 0.679 [16] | 0.679 |
| spurious_p0.0_root | 0.679 | 0.679 [64] | 0.679 | 0.679 [8] | 0.679 |
| spurious_p0.1_prox | 0.670 | 0.648 [128] | 0.648 | 0.648 [16] | 0.648 |
| spurious_p0.1_root | 0.692 | 0.665 [256] | 0.665 | 0.689 [64] | 0.689 |
| spurious_p0.25_prox | 0.658 | 0.607 [128] | 0.607 | 0.608 [256] | 0.608 |
| spurious_p0.25_root | 0.711 | 0.647 [512] | 0.648 | 0.705 [512] | 0.705 |
| spurious_p0.5_prox | 0.636 | 0.535 [128] | 0.535 | 0.537 [256] | 0.537 |
| spurious_p0.5_root | 0.744 | 0.611 [512] | 0.612 | 0.730 [512] | 0.731 |
| spurious_p1.0_prox | 0.595 | 0.400 [64] | 0.400 | 0.405 [256] | 0.406 |
| spurious_p1.0_root | 0.800 | 0.545 [512] | 0.549 | 0.775 [512] | 0.776 |
| realtext_tau0.45_prox | 0.567 | 0.458 [512] | 0.458 | 0.547 [512] | 0.547 |
| realtext_tau0.45_root | 0.655 | 0.505 [512] | 0.505 | 0.642 [32] | 0.645 |
| realtext_tau0.5_prox | 0.720 | 0.663 [128] | 0.663 | 0.712 [128] | 0.712 |
| realtext_tau0.5_root | 0.738 | 0.643 [128] | 0.643 | 0.728 [512] | 0.728 |
| realtext_tau0.6_prox | 0.640 | 0.640 [256] | 0.640 | 0.642 [8] | 0.642 |
| realtext_tau0.6_root | 0.642 | 0.640 [128] | 0.640 | 0.642 [8] | 0.642 |

## B. Pool scaling, causal@5 (n=30 per pool, seed 0)

| pool | PPR alpha 0.85 | PPR alpha 0.95 (tuned) | additive |
|---|---|---|---|
| 18 | 0.333 | 0.667 | 1.000 |
| 79 | 0.333 | 0.667 | 1.000 |
| 379 | 0.333 | 0.667 | 1.000 |
| 979 | 0.333 | 0.667 | 1.000 |
| 1504 | 0.333 | 0.667 | 0.989 |

## C. Eight domains, test split (15/domain), causal@5

| domain | tau | additive | mult 0.6 | mult 16 |
|---|---|---|---|---|
| plague | 0.55 | 1.000 | 0.378 | 1.000 |
| water | 0.55 | 1.000 | 0.378 | 1.000 |
| cyber | 0.6 | 1.000 | 0.289 | 1.000 |
| crime | 0.55 | 1.000 | 0.467 | 1.000 |
| housing | 0.55 | 0.978 | 0.400 | 1.000 |
| power | 0.55 | 1.000 | 0.378 | 1.000 |
| software-debugging | 0.6 | 1.000 | 0.444 | 1.000 |
| cybersecurity | 0.6 | 1.000 | 0.356 | 1.000 |
