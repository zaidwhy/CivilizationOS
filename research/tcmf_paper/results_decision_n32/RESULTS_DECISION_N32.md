# N32: decision accuracy with stronger judges (n=60, k=5, Wilson 95% CI)

| judge | no retrieval | oracle | cond | additive 4 | mult 0.6 | mult 16 | causal only | add vs mult16 (discordant, McNemar p) |
|---|---|---|---|---|---|---|---|---|
| meta-llama/llama-3.3-70b-instruct | 0.37 | 0.95 | clean | 0.87 | 0.67 | 0.88 | 0.87 | 0/1, p=1.000 |
| meta-llama/llama-3.3-70b-instruct | 0.37 | 0.95 | leaky | 0.73 | 0.60 | 0.72 | 0.77 | 1/0, p=1.000 |
| google/gemini-2.5-flash | 0.25 | 0.98 | clean | 0.95 | 0.53 | 0.97 | 0.93 | 0/1, p=1.000 |
| google/gemini-2.5-flash | 0.25 | 0.98 | leaky | 0.75 | 0.50 | 0.63 | 0.82 | 8/1, p=0.039 |
