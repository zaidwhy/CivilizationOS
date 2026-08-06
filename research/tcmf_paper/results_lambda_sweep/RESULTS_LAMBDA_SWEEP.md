# Recall@5 vs lambda, both fusion operators (N10 Fig 4 data)

Pure regime, pool 78 (300 scenarios/seed x 5 seeds = 1500 total, N01-scale pool). Mean [95% bootstrap CI].

| lambda | multiplicative recall@5 | additive recall@5 |
|---|---|---|
| 0.0 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| 0.1 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| 0.3 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| 0.6 | 0.0104 [0.0076, 0.0136] | 0.0689 [0.0620, 0.0758] |
| 1.0 | 0.1509 [0.1420, 0.1596] | 0.3662 [0.3611, 0.3713] |
| 1.5 | 0.3238 [0.3149, 0.3324] | 0.6578 [0.6549, 0.6604] |
| 2.0 | 0.4464 [0.4373, 0.4556] | 0.6713 [0.6696, 0.6733] |
| 2.4 | 0.5227 [0.5136, 0.5318] | 0.7122 [0.7064, 0.7182] |
| 3.0 | 0.6062 [0.5987, 0.6136] | 0.9509 [0.9449, 0.9569] |
| 4.0 | 0.6976 [0.6913, 0.7038] | 0.9998 [0.9993, 1.0000] |
| 5.0 | 0.7711 [0.7633, 0.7789] | 0.9998 [0.9993, 1.0000] |
| 6.0 | 0.8498 [0.8413, 0.8580] | 0.9998 [0.9993, 1.0000] |
| 8.0 | 0.9569 [0.9513, 0.9624] | 0.9998 [0.9993, 1.0000] |
| 10.0 | 0.9953 [0.9933, 0.9971] | 0.9998 [0.9993, 1.0000] |
| 15.0 | 1.0000 [1.0000, 1.0000] | 0.9998 [0.9993, 1.0000] |
| 20.0 | 1.0000 [1.0000, 1.0000] | 0.9998 [0.9993, 1.0000] |

- N03 tune-selected multiplicative lambda = 2.4: recall@5 = 0.5227 [0.5136, 0.5318] (this is also the grid's own 2.4 row, marked separately since it is the value a fair tune sweep actually picked, not the shipped default).
- Sanity check: this sweep's lambda=0.6/8 (mult) and lambda=4 (additive) points match `results_main_scale/results.json` to machine precision (asserted at runtime).
