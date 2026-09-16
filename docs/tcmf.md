# TCMF: a RAG fusion formula that failed its own benchmark, and the fix

Standard RAG is great for static knowledge bases. Embed documents, embed a query, return top-k by cosine similarity. That works.

But put RAG inside a running civilization where citizens have memories, councils deliberate on crises, and past decisions ripple into future ones, and similarity alone breaks down fast. Cosine similarity doesn't know that a drought *caused* today's food riot. It doesn't know that a council that voted against emergency grain reserves three weeks ago is directly responsible for the current famine. It retrieves memories that *sound like* the crisis, not memories that *led to* it.

That gap is what Temporal-Causal Memory Fusion (TCMF) tries to close for CivilizationOS. This document explains the design, the formula I shipped first, the benchmark that caught it being wrong, and the fix that's actually running today.

---

## The context: what CivilizationOS is

- 10 citizens live, work, and accumulate episodic memories over simulation ticks (the **AGORA** layer).
- Five specialist councils deliberate on injected crises (the **PANTHEON** layer).
- A 3-tier LLM router handles different reasoning loads: Ollama locally, Gemini Flash mid-tier, Claude/OpenRouter for the heaviest deliberation.

When a crisis hits, the responding council needs context. The naive answer is "embed the crisis question, retrieve top-k similar memories." TCMF is the better answer - or was supposed to be, before a benchmark found out it wasn't, the first time it shipped.

---

## Two streams, one score

TCMF fuses two independent information streams.

### Stream 1: AGORA (episodic, per-citizen)

The generative-agents formula (Park et al., 2023). Each citizen has a memory stream of timestamped observations, scored on relevance (cosine similarity to the query), recency (exponential decay since last access), and importance (a 1-10 poignancy score):

```python
score = w_rel * relevance + w_rec * recency + w_imp * importance
```

This ranks purely by how similar or recent a memory is. It knows nothing about causality.

### Stream 2: PANTHEON (causal, society-wide)

A NetworkX directed graph tracks what led to what:

```
drought (tick 20) -> emergency rationing (tick 25) -> black-market spike (tick 30) -> civil unrest (tick 45) -> riots (tick 60)
```

When a crisis fires, TCMF does a bounded BFS backward from the crisis node to find its causal ancestors, up to `max_depth` hops back.

---

## The formula that failed its own benchmark

The first version I shipped combined the two streams multiplicatively:

```
tcmf_score(m) = episodic_score(m, q) x (1 + lambda x causal_boost(m))
```

It looked reasonable - the causal term scales the episodic score up when a memory is causally relevant. It also scored **recall@5 of 0.02** on the exact task it was designed for: a 300-scenario benchmark, run against six baselines, where root-cause memories are constructed to be semantically *distant* from the crisis they caused (cosine similarity to the query around -0.05) while "loud" but causally-irrelevant distractor memories share the crisis's surface topic (cosine around 0.81). The causal signal alone, unfused, reaches recall@5 = 1.00 on this task - it is fully sufficient. The multiplicative fusion exploited essentially none of it.

The reason is arithmetic, not subtle: a root-cause memory's episodic score is near zero, because it doesn't read like the crisis. Multiplying a near-zero base by any boost, however large, stays near zero. The fusion could never lift the memory that mattered most, no matter how strongly the causal graph pointed at it.

**The fix was additive, not multiplicative:**

```
tcmf_score(m) = normalize(episodic_score(m, q)) + lambda * causal_boost(m)
```

Episodic scores are min-max normalized across the candidate pool first, so the causal term can compete on equal footing instead of being crushed by whatever the episodic score happens to be. In isolation (the additive operator alone, same scores as the multiplicative version), this recovers recall@5 = 1.00 - the full signal.

The version actually shipped in `TCMFRetriever` today makes one further, deliberate tradeoff on top of that: it also fixes a second, independent bug (below) that reweights which causal ancestor gets favored. That combination lands at **recall@5 = 0.76, recall@10 = 1.00, with the root-cause memory at rank 1** (root MRR 1.00) - a small amount of top-5 recall traded for making sure the single most important memory, the actual root cause, is the one the LLM sees first in a limited context window, not just present somewhere in the top ten.

There were three other real bugs the same benchmarking pass caught, each documented as its own fix in `api/memory/tcmf.py`:

- **Depth weighting was inverted.** The original weight, `1 - (depth-1)/max_depth`, gave the *direct* cause the highest weight and the deepest ancestor - the actual root cause - the lowest, backwards from the module docstring's own stated intent. Even after the additive fix alone, the root cause sat at mean rank 3.0. Inverting the weight so deeper ancestors score higher moved it to rank 1.0, with no cost to recall.
- **The crisis could leak a boost to itself.** The institution-scoped "weak ancestor" fallback didn't exclude the crisis event, so a crisis could occasionally boost memories that merely resembled itself, undermining the causal signal it was supposed to isolate.
- **Per-citizen pre-filtering discarded root-cause memories before the causal boost ever saw them.** Retrieving only each citizen's episodic top-k before fusion meant a low-relevance root-cause memory could be filtered out before the causal term had a chance to rescue it. The candidate pool now stays large through fusion, then gets cut down after.

I did not find any of this by inspection. The multiplicative formula reads fine on paper - it's a plausible design a reasonable engineer would ship without a benchmark to check it against. I found it because the benchmark was built first, run against the shipped code, and read honestly rather than assumed to agree with the design intent.

---

## Concrete example

Crisis: "Plague outbreak in the market district."

**Pure semantic RAG surfaces:**
- "Merchants reported strange symptoms near the well" - high similarity to "plague outbreak."
- "Children are sick, clinics are full" - high similarity.
- "City refused to fund quarantine infrastructure two weeks ago" - low similarity, ranks low or not at all.

**TCMF, with the quarantine refusal as a causal ancestor:**
- "City refused to fund quarantine infrastructure two weeks ago" - gets the causal boost, ranks at the top.
- The two symptom memories still rank on their own episodic merit.

The council's context now includes the *reason* the plague spread as fast as it did, not just descriptions of the symptoms - which changes what policy a council recommends.

---

## The shipped pipeline (current code)

```python
# 4. Normalized-additive fusion: minmax(episodic) + lambda * causal_boost.
max_depth_seen = max(ancestors.values(), default=1) or 1
epi = [sm.score for _, sm in raw]
lo, hi = (min(epi), max(epi)) if epi else (0.0, 0.0)
span = hi - lo

for cid, sm in raw:
    norm_epi = (sm.score - lo) / span if span > 1e-12 else 0.0
    depth_boost = self._causal_boost_for_memory(sm.memory, ancestors, max_depth_seen)
    score = norm_epi + self.causal_boost * depth_boost   # causal_boost = lambda, default 2.0
    fused.append((cid, sm.memory, score))
```

```python
def _causal_boost_for_memory(self, memory, ancestors, max_depth):
    if not ancestors or memory.embedding is None:
        return 0.0
    best = 0.0
    for eid, depth in ancestors.items():
        ev = self.graph.get_event(eid)
        if ev is None or ev.get("embedding") is None:
            continue
        sim = _cosine(memory.embedding, ev["embedding"])
        if sim >= self.causal_sim_threshold:
            # deeper ancestor = closer to the root cause = higher weight (the F5 fix).
            depth_weight = depth / max(max_depth, 1)
            best = max(best, sim * depth_weight)
    return best
```

Source: `api/memory/tcmf.py` (`TCMFRetriever`), `api/memory/causal_graph.py` (`CausalGraph`, BFS traversal), `api/memory/stream.py` (the episodic scoring formula).

---

## The implementation stack

- **NetworkX DiGraph** for the causal graph - free BFS, edge weights, Python-native, no graph database needed at this scale.
- **NumPy vector store**, no Chroma or Pinecone - at roughly 10 agents with a few hundred memories each, brute-force cosine over an in-memory matrix is exact and fast.
- **Asyncio throughout** - embedding calls are async, retrieval is non-blocking.
- **Embeddings are optional** - when none is available, relevance scores to 0 and the formula falls back to recency plus importance; the system runs in tests and in embedding-free mode without breaking.

---

## The honest tradeoffs

**What TCMF gains over plain episodic RAG:** surfaces root-cause memories similarity alone misses; the causal chain summary gives the LLM explicit historical structure to reason about; graceful degradation at every level (no embeddings, no causal graph, no crisis event ID each degrade cleanly rather than crash).

**What it costs:** the causal graph has to be maintained - events logged, links drawn. In CivilizationOS this happens automatically as the simulation runs; in a system without that, you'd need an event-logging pipeline and something to decide what caused what. `auto_link_predecessors()` can infer weak links from temporal proximity plus semantic similarity when explicit causal links aren't known, but inferred causality is noisy - useful for filling a sparse graph, not a substitute for explicit causal modeling.

There are three tunable parameters (`causal_boost`/lambda, `causal_sim_threshold`, `max_depth`). Getting them wrong either swamps the episodic signal or makes the causal boost irrelevant - see `research/tcmf_paper/FINDINGS.md` for the ablations that picked the shipped defaults, including the lambda-sensitivity sweep and the mixed-regime analysis that justifies fusion over using the causal signal alone.

**When to use TCMF vs. plain episodic RAG:** use it when your agent operates in a causally structured environment, where past events produce downstream effects that matter for the current decision. For a support chatbot over a static knowledge base, standard RAG is the right tool.

---

## What I'd change in v2

- **Use edge weights in the boost.** `link()` already stores a causal-strength weight per edge, but `_causal_boost_for_memory` doesn't use it yet - a strong direct cause should contribute more than a weak inferred link.
- **Add reflection-generated memories**, per the Stanford paper's periodic higher-level observations ("three crises in the health sector this month"), so councils can reason about patterns, not just individual incidents.
- **Cross-institution causal links** - a proper multi-institution graph would model how a Treasury decision cascades into a Military readiness crisis; the graph structure already supports it, retrieval just doesn't use cross-institution ancestors yet.

---

## Source

`api/memory/tcmf.py` (`TCMFRetriever`, `TCMFContext`), `api/memory/causal_graph.py` (`CausalGraph`), `api/memory/stream.py` (`MemoryStream`). The full benchmark - 300 scenarios, six baselines, the multiplicative-vs-additive comparison, and eleven further ablations (real embeddings, decision-quality effects, spurious-edge robustness, a second domain corpus) - lives in `research/tcmf_paper/` (152 tests, running in CI).

If you're building multi-agent systems where decisions have downstream effects: semantic similarity and causal relevance are not the same signal, and fusing them wrong is easy to do without a benchmark that specifically tries to catch it.
