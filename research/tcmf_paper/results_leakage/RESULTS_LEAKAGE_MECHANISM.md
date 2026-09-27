# N26b: leaked (causal-gold, non-gold) pairs by reachability

| setting | depth weights | leaked pairs | mult-only unreachable | both unreachable | reachable | mult recall@5 as lambda -> inf |
|---|---|---|---|---|---|---|
| spurious_p0.1 | prox | 9525 | 0.394 | 0.509 | 0.097 | 0.648 |
| spurious_p0.1 | root | 9525 | 0.252 | 0.002 | 0.746 | 0.689 |
| spurious_p0.25 | prox | 22287 | 0.388 | 0.515 | 0.097 | 0.608 |
| spurious_p0.25 | root | 22287 | 0.249 | 0.001 | 0.750 | 0.705 |
| spurious_p0.5 | prox | 45021 | 0.393 | 0.511 | 0.096 | 0.537 |
| spurious_p0.5 | root | 45021 | 0.252 | 0.001 | 0.748 | 0.731 |
| spurious_p1.0 | prox | 85584 | 0.396 | 0.508 | 0.096 | 0.406 |
| spurious_p1.0 | root | 85584 | 0.251 | 0.000 | 0.748 | 0.776 |
| realtext_tau0.45 | prox | 1968 | 0.293 | 0.094 | 0.613 | 0.547 |
| realtext_tau0.45 | root | 1968 | 0.232 | 0.034 | 0.734 | 0.645 |
| realtext_tau0.5 | prox | 585 | 0.246 | 0.291 | 0.463 | 0.712 |
| realtext_tau0.5 | root | 585 | 0.267 | 0.087 | 0.646 | 0.728 |
