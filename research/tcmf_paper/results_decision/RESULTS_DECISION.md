# TCMF Benchmark: Decision-Quality Tier

Scenarios: 60 | seed: 0 | model: qwen2.5:3b-instruct | k: 5 | causal threshold: 0.6

Each method's top-k retrieved memories are shown to the LLM council advisor, which must pick the true root cause from a fixed 4-way multiple choice (true cause + 3 external-shock decoys). `decision_acc` = mean correct. `causal@5` = recall over the causal-gold subset, reported alongside for comparison.

| method | causal@5 | decision_acc |
|---|---|---|
| semantic_rag | 0.12±0.17 | 0.35±0.48 |
| episodic | 0.02±0.07 | 0.25±0.43 |
| causal_only | 1.00±0.00 | 0.85±0.36 |
| graph_ppr | 0.90±0.15 | 0.78±0.41 |
| tcmf_mult | 0.42±0.20 | 0.50±0.50 |
| tcmf_add | 0.99±0.06 | 0.83±0.37 |
| tcmf_shipped | 0.93±0.15 | 0.97±0.18 |
| tcmf_rrf | 0.63±0.17 | 0.55±0.50 |
| no_retrieval | - | 0.32±0.47 |
| oracle | - | 0.95±0.22 |

Hypothesis HELD: retrieval choice changes the decision. Causal-recall methods (tcmf_add, tcmf_shipped, causal_only) scored clearly above the no_retrieval floor (0.32) toward the oracle ceiling (0.95), while the pure-symptom retrievers (semantic_rag, episodic) sat near that floor. The broken multiplicative fusion (tcmf_mult) lands in between at 0.50, mirroring its partial causal recall - the additive operator converts the same causal signal into correct decisions where the multiplicative one does not.
