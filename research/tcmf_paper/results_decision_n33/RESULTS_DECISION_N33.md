# N33: decisions from LLM-built graphs (n=60, background memories, tau=0.60)

| judge | graph | add prox | mult prox | add root | mult root |
|---|---|---|---|---|---|
| meta-llama/llama-3.3-70b-instruct | true chain | 0.78 | 0.82 | 0.80 | 0.78 |
| meta-llama/llama-3.3-70b-instruct | llama-70b | 0.78 | 0.68 | 0.77 | 0.77 |
| meta-llama/llama-3.3-70b-instruct | gemini-flash | 0.80 | 0.77 | 0.68 | 0.67 |
| google/gemini-2.5-flash | true chain | 0.97 | 0.98 | 0.98 | 0.98 |
| google/gemini-2.5-flash | llama-70b | 0.88 | 0.85 | 0.75 | 0.77 |
| google/gemini-2.5-flash | gemini-flash | 0.92 | 0.87 | 0.73 | 0.72 |
| qwen2.5:3b-instruct | true chain | 0.87 | 0.88 | 0.92 | 0.92 |
| qwen2.5:3b-instruct | llama-70b | 0.85 | 0.80 | 0.77 | 0.80 |
| qwen2.5:3b-instruct | gemini-flash | 0.85 | 0.78 | 0.85 | 0.85 |
