# N31: causal graphs built by an LLM (real text, 6 domains, n=120, tau=0.60)

| graph | weights | add l=4 | mult l=16 | add - mult16 [95% CI] | causal alone | best mult (exploratory) | leaked pairs | rho<1 | only-mult-fails | only-add-fails |
|---|---|---|---|---|---|---|---|---|---|---|
| true chain | prox | 0.640 | 0.642 | -0.002 [-0.005, +0.000] | 0.678 | 0.642 | 0 | - | - | - |
| no graph | prox | 0.075 | 0.075 | +0.000 [+0.000, +0.000] | 0.322 | 0.075 | 0 | - | - | - |
| meta-llama/llama-3.3-70b-instruct | prox | 0.633 | 0.633 | +0.000 [+0.000, +0.000] | 0.675 | 0.633 | 53 | 0.94 | 0.17 | 0.04 |
| google/gemini-2.5-flash | prox | 0.638 | 0.637 | +0.002 [+0.000, +0.005] | 0.683 | 0.637 | 97 | 0.99 | 0.38 | 0.00 |
| qwen2.5:3b-instruct | prox | 0.458 | 0.460 | -0.002 [-0.008, +0.003] | 0.552 | 0.460 | 117 | 0.72 | 0.18 | 0.04 |
| mistral:7b | prox | 0.442 | 0.442 | +0.000 [-0.005, +0.005] | 0.545 | 0.442 | 20 | 0.75 | 0.15 | 0.00 |
| true chain | root | 0.642 | 0.642 | +0.000 [+0.000, +0.000] | 0.678 | 0.642 | 0 | - | - | - |
| no graph | root | 0.075 | 0.075 | +0.000 [+0.000, +0.000] | 0.322 | 0.075 | 0 | - | - | - |
| meta-llama/llama-3.3-70b-instruct | root | 0.630 | 0.630 | +0.000 [+0.000, +0.000] | 0.673 | 0.630 | 53 | 0.94 | 0.17 | 0.04 |
| google/gemini-2.5-flash | root | 0.622 | 0.632 | -0.010 [-0.022, -0.002] | 0.673 | 0.632 | 97 | 0.99 | 0.30 | 0.00 |
| qwen2.5:3b-instruct | root | 0.457 | 0.458 | -0.002 [-0.008, +0.003] | 0.547 | 0.460 | 117 | 0.72 | 0.14 | 0.03 |
| mistral:7b | root | 0.442 | 0.442 | +0.000 [+0.000, +0.000] | 0.543 | 0.442 | 20 | 0.75 | 0.00 | 0.00 |

## Graph quality

| model | calls | unparsed | ancestor precision | ancestor recall | root found | false ancestors / scenario | false-ancestor kinds | edges (chain/shortcut/reversed/false) |
|---|---|---|---|---|---|---|---|---|
| meta-llama/llama-3.3-70b-instruct | 814 | 0 | 0.50 | 0.97 | 1.00 | 3.63 | {'decision': 333, 'crisis': 100, 'city': 3} | 293/292/0/1091 |
| google/gemini-2.5-flash | 902 | 3 | 0.44 | 0.97 | 1.00 | 4.51 | {'crisis': 163, 'decision': 375, 'city': 3} | 289/298/0/1368 |
| qwen2.5:3b-instruct | 778 | 3 | 0.38 | 0.62 | 0.69 | 4.37 | {'decision': 296, 'crisis': 188, 'city': 40} | 119/126/0/976 |
| mistral:7b | 529 | 0 | 0.47 | 0.62 | 0.82 | 2.45 | {'decision': 212, 'crisis': 71, 'city': 11} | 118/141/0/455 |
