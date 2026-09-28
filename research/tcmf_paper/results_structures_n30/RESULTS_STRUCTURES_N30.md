# N30: graph families and the leaked-pair map

## A. Recall@5 (all gold), mixed regime pool 80, n=600 per row

| family | condition | weights | add l=4 | mult l=16 | best mult (oracle) | causal | clean: add need median | clean: mult need median | add l=4 suffices | mult l=16 suffices |
|---|---|---|---|---|---|---|---|---|---|---|
| chain3 | clean | prox | 0.651 | 0.651 | 0.651 | 0.522 | 1.73 | 3.01 | 1.00 | 1.00 |
| chain3 | clean | root | 0.651 | 0.651 | 0.651 | 0.522 | 0.87 | 1.51 | 1.00 | 1.00 |
| chain3 | onleak | prox | 0.739 | 0.502 | 0.504 | 0.750 | - | - | 0.00 | 0.00 |
| chain3 | onleak | root | 0.770 | 0.657 | 0.702 | 0.999 | 1.40 | 6.53 | 1.00 | 0.52 |
| chain3 | clutter | prox | 0.377 | 0.394 | 0.397 | 0.354 | 1.54 | 1.51 | 0.17 | 0.12 |
| chain3 | clutter | root | 0.132 | 0.177 | 0.269 | 0.111 | 1.29 | 1.27 | 0.08 | 0.07 |
| chain4 | clean | prox | 0.675 | 0.674 | 0.674 | 0.612 | 2.70 | 5.19 | 0.99 | 0.99 |
| chain4 | clean | root | 0.674 | 0.674 | 0.674 | 0.611 | 0.90 | 1.74 | 1.00 | 1.00 |
| chain4 | onleak | prox | 0.595 | 0.402 | 0.406 | 0.600 | - | - | 0.00 | 0.00 |
| chain4 | onleak | root | 0.801 | 0.727 | 0.772 | 0.996 | 1.21 | 4.76 | 1.00 | 0.92 |
| chain4 | clutter | prox | 0.360 | 0.377 | 0.377 | 0.346 | 2.08 | 2.60 | 0.07 | 0.05 |
| chain4 | clutter | root | 0.142 | 0.181 | 0.207 | 0.130 | 1.13 | 1.79 | 0.14 | 0.10 |
| chain6 | clean | prox | 0.611 | 0.711 | 0.713 | 0.712 | 4.58 | 9.60 | 0.10 | 0.98 |
| chain6 | clean | root | 0.702 | 0.713 | 0.713 | 0.712 | 0.92 | 1.92 | 1.00 | 1.00 |
| chain6 | onleak | prox | 0.428 | 0.288 | 0.289 | 0.538 | - | - | 0.00 | 0.00 |
| chain6 | onleak | root | 0.712 | 0.710 | 0.714 | 0.712 | 1.08 | 3.24 | 1.00 | 1.00 |
| chain6 | clutter | prox | 0.318 | 0.346 | 0.348 | 0.284 | 5.88 | 5.09 | 0.01 | 0.01 |
| chain6 | clutter | root | 0.183 | 0.198 | 0.198 | 0.161 | 1.23 | 2.92 | 0.32 | 0.14 |
| diamond | clean | prox | 0.674 | 0.674 | 0.674 | 0.612 | 1.80 | 3.46 | 0.99 | 0.99 |
| diamond | clean | root | 0.674 | 0.674 | 0.674 | 0.611 | 0.90 | 1.74 | 1.00 | 1.00 |
| diamond | onleak | prox | 0.749 | 0.403 | 0.406 | 0.800 | - | - | 0.00 | 0.00 |
| diamond | onleak | root | 0.633 | 0.502 | 0.548 | 0.997 | 1.46 | 10.65 | 1.00 | 0.36 |
| diamond | clutter | prox | 0.461 | 0.446 | 0.452 | 0.442 | 5.19 | 1.70 | 0.09 | 0.04 |
| diamond | clutter | root | 0.092 | 0.138 | 0.209 | 0.084 | 3.16 | 1.60 | 0.05 | 0.04 |
| two_roots | clean | prox | 0.704 | 0.704 | 0.705 | 0.671 | 1.82 | 3.62 | 0.99 | 0.99 |
| two_roots | clean | root | 0.704 | 0.704 | 0.704 | 0.671 | 0.91 | 1.81 | 1.00 | 1.00 |
| two_roots | onleak | prox | 0.623 | 0.336 | 0.339 | 0.667 | - | - | 0.00 | 0.00 |
| two_roots | onleak | root | 0.677 | 0.537 | 0.595 | 0.830 | 1.48 | 14.52 | 1.00 | 0.27 |
| two_roots | clutter | prox | 0.431 | 0.426 | 0.432 | 0.408 | 5.03 | 2.36 | 0.11 | 0.05 |
| two_roots | clutter | root | 0.085 | 0.134 | 0.182 | 0.072 | 3.10 | 2.47 | 0.02 | 0.02 |
| tree | clean | prox | 0.713 | 0.713 | 0.713 | 0.712 | 2.75 | 5.76 | 0.99 | 0.99 |
| tree | clean | root | 0.713 | 0.713 | 0.713 | 0.713 | 0.92 | 1.92 | 1.00 | 1.00 |
| tree | onleak | prox | 0.554 | 0.288 | 0.290 | 0.571 | - | - | 0.00 | 0.00 |
| tree | onleak | root | 0.714 | 0.550 | 0.636 | 0.713 | 1.23 | 6.15 | 1.00 | 0.87 |
| tree | clutter | prox | 0.401 | 0.400 | 0.402 | 0.374 | 6.54 | 3.73 | 0.02 | 0.01 |
| tree | clutter | root | 0.103 | 0.134 | 0.155 | 0.094 | 2.65 | 3.29 | 0.09 | 0.04 |
| side_cause | clean | prox | 0.686 | 0.713 | 0.713 | 0.712 | 3.67 | 7.68 | 0.78 | 0.99 |
| side_cause | clean | root | 0.713 | 0.713 | 0.714 | 0.713 | 0.92 | 1.92 | 1.00 | 1.00 |
| side_cause | onleak | prox | 0.425 | 0.286 | 0.287 | 0.462 | - | - | 0.00 | 0.00 |
| side_cause | onleak | root | 0.714 | 0.700 | 0.714 | 0.713 | 1.13 | 3.93 | 1.00 | 0.99 |
| side_cause | clutter | prox | 0.325 | 0.361 | 0.364 | 0.296 | 6.32 | 3.72 | 0.02 | 0.01 |
| side_cause | clutter | root | 0.139 | 0.188 | 0.207 | 0.119 | 1.58 | 2.06 | 0.14 | 0.07 |

## B. Leaked pairs (four-event chain, proximate weights)

| leak | pairs | rho<1 | mult-only wrong (Prop 1a) | add-only wrong (Prop 3) | both wrong | both right | median rho | median beta |
|---|---|---|---|---|---|---|---|---|
| onleak | 34251 | 1.00 | 0.40 | 0.00 | 0.51 | 0.09 | 0.51 | 1.01 |
| clutter | 34614 | 0.52 | 0.13 | 0.07 | 0.19 | 0.62 | 0.98 | 0.67 |
