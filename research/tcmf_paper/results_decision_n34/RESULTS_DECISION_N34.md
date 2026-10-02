# N34: decision accuracy at n=120 (k=5, Wilson 95% CI)

| judge | no retrieval | oracle | cond | add 4 | mult 0.6 | mult 16 | causal | add vs mult16 (disc, p) |
|---|---|---|---|---|---|---|---|---|
| qwen2.5:3b-instruct | 0.325 | 0.950 | clean | 0.850 | 0.508 | 0.858 | 0.883 | 0/1, p=1.0000 |
| qwen2.5:3b-instruct | 0.325 | 0.950 | leaky | 0.658 | 0.408 | 0.592 | 0.775 | 10/2, p=0.0386 |
| meta-llama/llama-3.3-70b-instruct | 0.342 | 0.950 | clean | 0.875 | 0.633 | 0.883 | 0.875 | 0/1, p=1.0000 |
| meta-llama/llama-3.3-70b-instruct | 0.342 | 0.950 | leaky | 0.683 | 0.575 | 0.675 | 0.792 | 3/2, p=1.0000 |
| google/gemini-2.5-flash | 0.267 | 0.967 | clean | 0.958 | 0.517 | 0.958 | 0.942 | 1/1, p=1.0000 |
| google/gemini-2.5-flash | 0.267 | 0.967 | leaky | 0.658 | 0.483 | 0.600 | 0.825 | 10/3, p=0.0923 |
