# N25: transfer of a fixed fusion weight to settings it was not tuned on

## mixed_pool80 (n=1500, threshold=0.45)

| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |
|---|---|---|---|---|---|
| add_l4 | 0.679 | 0.798 | 1.000 | 0.199 | 3.0 |
| mult_l0.6 | 0.188 | 0.292 | 0.059 | 0.382 | 43.2 |
| mult_l8 | 0.673 | 0.795 | 0.987 | 0.201 | 3.4 |
| mult_l16 | 0.679 | 0.798 | 1.000 | 0.198 | 3.0 |
| causal_only | 0.613 | 0.638 | 1.000 | 0.032 | 3.0 |

## realtext_6dom (n=120, threshold=0.6)

| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |
|---|---|---|---|---|---|
| add_l4 | 0.640 | 1.000 | 0.994 | 0.108 | 3.4 |
| mult_l0.6 | 0.307 | 0.872 | 0.392 | 0.179 | 11.3 |
| mult_l8 | 0.642 | 1.000 | 1.000 | 0.104 | 3.2 |
| mult_l16 | 0.642 | 1.000 | 1.000 | 0.104 | 3.2 |
| causal_only | 0.678 | 0.850 | 1.000 | 0.196 | 3.2 |

## realtext_8dom_test (n=80, threshold=0.6)

| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |
|---|---|---|---|---|---|
| add_l4 | 0.665 | 1.000 | 0.988 | 0.181 | 3.3 |
| mult_l0.6 | 0.323 | 0.855 | 0.371 | 0.250 | 11.2 |
| mult_l8 | 0.672 | 1.000 | 1.000 | 0.181 | 3.2 |
| mult_l16 | 0.672 | 1.000 | 1.000 | 0.181 | 3.2 |
| causal_only | 0.715 | 0.843 | 1.000 | 0.287 | 3.2 |

## realtext_6dom_leaky_tau045 (n=120, threshold=0.45)

| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |
|---|---|---|---|---|---|
| add_l4 | 0.567 | 0.973 | 0.544 | 0.600 | 7.0 |
| mult_l0.6 | 0.378 | 0.862 | 0.211 | 0.629 | 10.7 |
| mult_l8 | 0.512 | 0.965 | 0.453 | 0.600 | 8.3 |
| mult_l16 | 0.527 | 0.965 | 0.478 | 0.600 | 8.1 |
| causal_only | 0.730 | 0.952 | 0.883 | 0.500 | 4.3 |

## mixed_pool80_spurious_p1 (n=1500, threshold=0.45)

| arm | recall@5 | recall@10 | causal@5 | semantic@5 | root_rank |
|---|---|---|---|---|---|
| add_l4 | 0.595 | 0.600 | 0.324 | 1.000 | 24.0 |
| mult_l0.6 | 0.393 | 0.400 | 0.000 | 0.984 | 43.3 |
| mult_l8 | 0.401 | 0.412 | 0.002 | 1.000 | 24.0 |
| mult_l16 | 0.403 | 0.419 | 0.005 | 1.000 | 24.0 |
| causal_only | 0.600 | 0.619 | 0.333 | 1.000 | 24.0 |
