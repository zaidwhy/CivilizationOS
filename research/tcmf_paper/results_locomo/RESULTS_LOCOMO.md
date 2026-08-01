# Does the TCMF regime occur in LoCoMo?

10 conversations, 273 multi-hop questions (category 1, >= 2 annotated evidence spans). Encoder: `nomic-embed-text`.

Rank every unit of the conversation by cosine similarity to the question, then see where the annotated gold evidence lands.

| unit | nomic prefix | pool | median worst-gold rank | recall@5 [95% CI] | recall@10 | gold outside top-5 |
|---|---|---|---|---|---|---|
| turn | no | 597 | 153 | 0.066 [0.045, 0.091] | 0.122 | 98.2% |
| turn | yes | 597 | 138 | 0.112 [0.085, 0.141] | 0.172 | 97.1% |
| session | no | 28 | 12 | 0.505 [0.465, 0.545] | 0.706 | 77.7% |
| session | yes | 28 | 12 | 0.477 [0.436, 0.517] | 0.703 | 79.1% |

**Report the session rows.** Retrieving single dialogue turns makes semantic search look far worse than it is; sessions are the granularity real systems use.

- At session granularity, assembling the full evidence set takes a median of 12 of 28 sessions.
- recall@5 is 0.505, and 77.7% of questions have a needed session outside the top 5.
- This shows semantic similarity is INSUFFICIENT. It does not show that causal structure is the remedy; LoCoMo ships no causal graph. See `locomo_regime.py`.
