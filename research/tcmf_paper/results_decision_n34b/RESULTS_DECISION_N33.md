# N33: decisions from LLM-built graphs (n=60, background memories, tau=0.60)

| judge | graph | add prox | mult prox | add root | mult root |
|---|---|---|---|---|---|
| qwen2.5:3b-instruct | true chain | 0.88 | 0.90 | 0.93 | 0.93 |
| qwen2.5:3b-instruct | llama-70b | 0.88 | 0.84 | 0.78 | 0.80 |
| qwen2.5:3b-instruct | gemini-flash | 0.88 | 0.82 | 0.78 | 0.78 |
| meta-llama/llama-3.3-70b-instruct | true chain | 0.83 | 0.86 | 0.90 | 0.89 |
| meta-llama/llama-3.3-70b-instruct | llama-70b | 0.82 | 0.75 | 0.75 | 0.74 |
| meta-llama/llama-3.3-70b-instruct | gemini-flash | 0.82 | 0.80 | 0.70 | 0.68 |
| google/gemini-2.5-flash | true chain | 0.97 | 0.97 | 0.98 | 0.98 |
| google/gemini-2.5-flash | llama-70b | 0.88 | 0.87 | 0.70 | 0.72 |
| google/gemini-2.5-flash | gemini-flash | 0.91 | 0.87 | 0.68 | 0.69 |
