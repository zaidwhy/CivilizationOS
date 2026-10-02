# N34 summary: n=120, Holm-corrected exact McNemar

## Leaky retrieval: additive 4 vs multiplicative 16 (3 tests)

| judge | add | mult16 | add-only / mult-only | p | p (Holm) |
|---|---|---|---|---|---|
| Qwen2.5-3B | 0.658 | 0.592 | 10/2 | 0.0386 | 0.1157 |
| Llama-3.3-70B | 0.683 | 0.675 | 3/2 | 1.0000 | 1.0000 |
| Gemini-2.5-Flash | 0.658 | 0.600 | 10/3 | 0.0923 | 0.1846 |

## True chain vs LLM-built graph, additive, prox weights (6 tests)

| judge | graph | true | graph acc | loss (pts) | true-only/graph-only | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| Qwen2.5-3B | llama-70b | 0.883 | 0.875 | +0.8 | 6/5 | 1.0000 | 1.0000 |
| Qwen2.5-3B | gemini-flash | 0.883 | 0.875 | +0.8 | 8/7 | 1.0000 | 1.0000 |
| Llama-3.3-70B | llama-70b | 0.833 | 0.817 | +1.7 | 10/8 | 0.8145 | 1.0000 |
| Llama-3.3-70B | gemini-flash | 0.833 | 0.825 | +0.8 | 12/11 | 1.0000 | 1.0000 |
| Gemini-2.5-Flash | llama-70b | 0.975 | 0.883 | +9.2 | 13/2 | 0.0074 | 0.0443 |
| Gemini-2.5-Flash | gemini-flash | 0.975 | 0.908 | +6.7 | 9/1 | 0.0215 | 0.1074 |

## True chain vs LLM-built graph, additive, root weights (6 tests)

| judge | graph | true | graph acc | loss (pts) | true-only/graph-only | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| Qwen2.5-3B | llama-70b | 0.925 | 0.783 | +14.2 | 22/5 | 0.0015 | 0.0030 |
| Qwen2.5-3B | gemini-flash | 0.925 | 0.783 | +14.2 | 21/4 | 0.0009 | 0.0027 |
| Llama-3.3-70B | llama-70b | 0.900 | 0.750 | +15.0 | 26/8 | 0.0029 | 0.0030 |
| Llama-3.3-70B | gemini-flash | 0.900 | 0.700 | +20.0 | 32/8 | 0.0002 | 0.0007 |
| Gemini-2.5-Flash | llama-70b | 0.983 | 0.700 | +28.3 | 35/1 | 0.0000 | 0.0000 |
| Gemini-2.5-Flash | gemini-flash | 0.983 | 0.675 | +30.8 | 37/0 | 0.0000 | 0.0000 |
