# TCMF -> Publishable Paper: Working Plan (grounded in the real implementation)

Status: living document. Owner: Zaid Ali Syed (solo first author). Reviewer-substitute
role filled during drafting; final draft to be cross-checked with a field expert before
submission.

> This plan replaces the earlier "Converting TCMF into a Publishable Paper" doc, which was
> written without access to the code and mistook TCMF for two unrelated projects
> (trust-aware matrix factorization for recommenders, and a tensor cross-modality fusion net
> for remote sensing). None of that literature, none of those venues, apply here. Only the
> generic paper skeleton from that doc is reused.

---

## Phase 0 - Locked framing (do not drift from this)

**What TCMF is.** Temporal-Causal Memory Fusion: a retrieval / re-ranking method for
LLM-agent episodic memory. It fuses two signals:

1. **Episodic salience** (AGORA stream) - the generative-agents formula
   `relevance x recency x importance` (Park et al., 2023), computed per agent over a
   `MemoryStream`.
2. **Causal proximity** (PANTHEON stream) - a bounded BFS backward through a directed
   causal event graph from the current crisis node, giving every past event a depth. A
   memory earns a depth-weighted boost when it is embedding-similar to a causal ancestor.

Fused score for memory `m` given crisis `q`:

```
tcmf_score(m) = episodic_score(m, q) x (1 + lambda x causal_boost(m))
causal_boost(m) = max over ancestors a of [ cos(emb(m), emb(a)) * (1 - (depth(a)-1)/max_depth) ]
                  for cos(emb(m), emb(a)) >= threshold
```

**One-sentence contribution.** *For agents making decisions in causally structured
environments, re-ranking retrieved episodic memories by proximity to the current crisis's
causal ancestors surfaces root-cause memories that semantic similarity alone buries, improving
causal-ancestor retrieval and downstream decision quality over standard and graph-structured
RAG baselines.*

**Field / reviewers.** LLM agents, agent memory, retrieval-augmented generation. NOT vision,
NOT recommender systems, NOT remote sensing.

**The claim only becomes a paper once it is measured.** That is Phase 2-3.

---

## Phase 1 - Related work (the correct neighbourhood)

Replaces the wrong Table 1. Position TCMF against:

| Work | Retrieval signal | Structure used | Decision-focused? | How TCMF differs |
|------|------------------|----------------|-------------------|------------------|
| Generative Agents (Park et al., 2023) | relevance+recency+importance | none | agent behaviour | TCMF's episodic base; TCMF adds causal re-ranking |
| GraphRAG (Edge et al., 2024) | community summaries over a KG | knowledge graph | QA / summarization | TCMF re-ranks episodic memories by *causal ancestry*, not community structure |
| HippoRAG (2024) | personalized PageRank over a KG | knowledge graph | multi-hop QA | TCMF uses *directed causal* depth from the crisis, not PPR over an open KG |
| MemGPT (Packer et al., 2023) | paged memory management | none | long-context agents | orthogonal; TCMF is a ranking signal, could sit inside MemGPT |
| Temporal-KG / causal-RAG line | time- or causally-aware retrieval | temporal/causal graph | QA | TCMF's specific fusion (episodic salience x causal-ancestor proximity) + decision eval |

TCMF's defensible wedge is narrow but real: **causal-ancestor re-ranking of episodic agent
memory, evaluated on decision quality.** Nobody in the table does exactly this.

Citations to pin down precisely during drafting (arXiv IDs / DOIs verified at write time -
do NOT cite from memory).

---

## STATUS (2026-07-21): go/no-go gate run. See FINDINGS.md.

Gate result: **GREEN.** (1) The causal signal is strong (causal_only recall@5 = 1.00) but the
**shipped multiplicative TCMF fusion exploits none of it** (recall@5 = 0.00, l-ablation flat).
(2) A normalized **additive** fusion of the identical scores recovers it (1.00). (3) In a
**mixed regime** (causal-gold + semantic-gold, `mixed.py`) additive TCMF **strictly beats every
single-signal baseline** at recall@10 (0.98 vs causal_only 0.79, semantic 0.51, graph_ppr 0.80,
shipped 0.74) and **degrades gracefully** under causal-graph edge dropout. The paper's
contribution is now sharp and defensible: **"causal-ancestor re-ranking of agent memory helps;
the fusion operator is decisive - multiplicative fusion suppresses the signal, additive fusion
recovers both causally- and semantically-relevant evidence and degrades gracefully as the graph
decays."** Four code-level defects in `TCMFRetriever` were also surfaced (fusion form, crisis
self-ancestor leak, depth-weight direction, pre-fusion per-citizen prune). See FINDINGS.md (F1-F7).

## Phase 2 - Benchmark (the go/no-go gate) - BUILT + RUN

Synthetic, controlled, fully offline and deterministic. The mechanism under test is the
**real** `api.memory.tcmf.TCMFRetriever` running on controlled inputs. See
`tcmfbench/` and `README.md`. Core design:

- A crisis sits at the end of an authored causal chain. The **root cause** has a topic
  distinct from the crisis surface, so it is *semantically far* from the crisis but
  *causally central*.
- **Distractor** memories share the crisis surface topic (semantically near, causally
  irrelevant) and are given high importance - the "loud symptom" that fools semantic and
  episodic retrieval. This is the deliberately hard case.
- **Gold** = witness memories of causal-ancestor events; the primary target is the
  root-cause witness memory.

Ground truth is known because we author the chain. Metrics: causal-ancestor recall@k,
root-cause rank / MRR, nDCG@k. Decision-quality proxy: whether the root-cause memory reaches
the top-k the council actually reads.

**Go/no-go:** if TCMF does not clearly beat semantic RAG on causal-ancestor recall here,
stop and fix TCMF (edge weights, per-citizen pruning, reflection) before writing.

---

## Phase 3 - Baselines and ablations - BUILT

Baselines: random, recency, **semantic RAG**, **episodic-only** (real pipeline, lambda=0),
causal-only, **graph PPR** (HippoRAG-style). Ablations: lambda sweep, threshold sweep,
max_depth, explicit vs auto-linked edges, edge-weight-aware boost (the "v2 one-liner"),
per-citizen top-8 pruning stress test. All runs report mean +/- std over seeds.

---

## Phase 4 - Analysis and honest limitations - IN PROGRESS

Done: fusion-operator study, depth-direction, difficulty sweep, mixed-regime complementarity,
edge-dropout robustness, and a **real-text tier** (Ollama nomic-embed-text, 6 domains) showing
the effect survives real embedding geometry once the anisotropic threshold is retuned to 0.60.
The four `TCMFRetriever` defects are fixed (all 66 tests pass). Remaining: latency of BFS vs
plain retrieval; a second encoder; scaling the real-text tier.

## Phase 5 - Write-up

Standard empirical-ML skeleton, ~8 pages, open code + benchmark generator.

## Phase 6 - Venue

arXiv preprint immediately; submit in parallel to a language-agents / LLM-memory workshop or
COLM. Not NeurIPS/CVPR main track for a solo first paper.
</content>
</invoke>
