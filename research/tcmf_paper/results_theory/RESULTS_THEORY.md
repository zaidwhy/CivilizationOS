# Required lambda per fusion operator

Pool 80 candidates, 20 distractors, 10 seeds. `clean=True, favor_root=False, threshold=0.45`.

| seed | mult needs | additive needs (uniform bound) | e(root) | max e(distractor) |
|---|---|---|---|---|
| 1 | 3.64 | 3.49 | 1.177 | 2.406 |
| 2 | 3.11 | 3.32 | 1.241 | 2.405 |
| 3 | 5.88 | 3.48 | 0.950 | 2.552 |
| 4 | 5.54 | 3.55 | 0.961 | 2.457 |
| 5 | 5.63 | 3.41 | 0.962 | 2.551 |
| 6 | 3.78 | 3.45 | 1.170 | 2.451 |
| 7 | unreachable | unreachable | 0.958 | 2.478 |
| 8 | 3.48 | 3.64 | 1.259 | 2.463 |
| 9 | 4.65 | 3.55 | 1.077 | 2.487 |
| 10 | 9.26 | 3.49 | 0.681 | 2.485 |

- Multiplicative requirement spans 3.11 to 9.26 (3.0x), plus 1 scenario(s) no lambda solves.
- Additive requirement spans 3.32 to 3.64 (1.10x).
- Unpromotable root/distractor pairs: 1 of 200.
- The shipped lambda = 4.0 clears the additive bound on every solvable seed: True.
