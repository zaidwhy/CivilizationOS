# N27: decision accuracy, qwen2.5:3b-instruct, n=60, k=5 (Wilson 95% CI)

| condition | arm | accuracy [95% CI] |
|---|---|---|
| clean (tau=0.6) | add_l4 | 0.83 [0.72, 0.91] |
| clean (tau=0.6) | mult_l0.6 | 0.50 [0.38, 0.62] |
| clean (tau=0.6) | mult_l16 | 0.83 [0.72, 0.91] |
| clean (tau=0.6) | causal_only | 0.85 [0.74, 0.92] |
| leaky (tau=0.45) | add_l4 | 0.68 [0.56, 0.79] |
| leaky (tau=0.45) | mult_l0.6 | 0.42 [0.30, 0.54] |
| leaky (tau=0.45) | mult_l16 | 0.57 [0.44, 0.68] |
| leaky (tau=0.45) | causal_only | 0.77 [0.65, 0.86] |

clean: additive vs mult16 discordant 0/0, exact McNemar p=1.000; additive vs mult0.6 discordant 21/1, p=1.1e-05

leaky: additive vs mult16 discordant 7/0, exact McNemar p=0.016; additive vs mult0.6 discordant 17/1, p=0.000145

Published clean arms reproduced: {'add_l4': 0.83, 'mult_l0.6': 0.5, 'causal_only': 0.85} (published: tcmf_add 0.83, tcmf_mult 0.50, causal_only 0.85)
