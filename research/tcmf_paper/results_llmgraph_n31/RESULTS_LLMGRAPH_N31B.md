# N31b: LLM-built graphs with a memory for every background event (n=120, tau=0.6, 16.0 memories added per scenario)

| graph | weights | add l=4 | mult l=16 | add - mult16 [95% CI] | causal alone | leaked pairs | rho<1 | only-mult-fails | only-add-fails |
|---|---|---|---|---|---|---|---|---|---|
| true chain | prox | 0.625 | 0.627 | -0.002 [-0.005, +0.000] | 0.652 | 228 | 0.51 | 0.05 | 0.01 |
| true chain | root | 0.640 | 0.640 | +0.000 [+0.000, +0.000] | 0.655 | 228 | 0.51 | 0.05 | 0.04 |
| google_gemini-2.5-flash | prox | 0.580 | 0.560 | +0.020 [+0.007, +0.033] | 0.582 | 1644 | 0.56 | 0.11 | 0.01 |
| google_gemini-2.5-flash | root | 0.312 | 0.313 | -0.002 [-0.010, +0.007] | 0.322 | 1644 | 0.56 | 0.08 | 0.03 |
| meta-llama_llama-3.3-70b-instruct | prox | 0.580 | 0.568 | +0.012 [+0.000, +0.023] | 0.582 | 1368 | 0.53 | 0.08 | 0.03 |
| meta-llama_llama-3.3-70b-instruct | root | 0.385 | 0.390 | -0.005 [-0.012, +0.000] | 0.388 | 1368 | 0.53 | 0.06 | 0.04 |
| qwen2.5_3b-instruct | prox | 0.317 | 0.313 | +0.003 [-0.008, +0.015] | 0.352 | 1253 | 0.58 | 0.13 | 0.05 |
| qwen2.5_3b-instruct | root | 0.277 | 0.280 | -0.003 [-0.017, +0.010] | 0.313 | 1253 | 0.58 | 0.11 | 0.05 |
