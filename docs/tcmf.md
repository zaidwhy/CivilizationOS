# TCMF: A RAG Variant I Designed for Multi-Agent Simulations (and the Tradeoffs)

Standard RAG is great for static knowledge bases. Embed documents, embed a query, return top-k by cosine similarity. That works.

But put RAG inside a running civilization where 40 citizens have memories, councils deliberate on crises, and past decisions ripple into future ones, and similarity alone breaks down fast.

The problem is simple: cosine similarity doesn't know that last month's drought *caused* today's food riot. It doesn't know that the council that voted against emergency grain reserves three weeks ago is directly responsible for the current famine. It retrieves memories that *sound like* the crisis, not memories that *led to* it.

That gap is what I wanted to close. This post explains the retrieval design I built for CivilizationOS, a multi-agent sim I've been working on, and the honest tradeoffs that come with it.

---

## The context: what CivilizationOS is

CivilizationOS is a multi-agent simulation where:

- 40+ citizens live, work, and accumulate episodic memories over simulation ticks (the **AGORA** layer)
- Specialist councils (Military, Health, Treasury, Senate) deliberate on injected crises (the **PANTHEON** layer)
- A 3-tier LLM router handles different reasoning loads: Ollama locally for lightweight calls, Gemini Flash for mid-tier, Claude Sonnet for complex deliberation

When a crisis hits, say a plague outbreak at tick 80, the Health Council needs to deliberate. It needs context. The question is: what context, and ranked how?

The naive answer is "embed the crisis question, retrieve top-k similar memories." The better answer is what TCMF computes.

---

## Two streams, one score

TCMF fuses two independent information streams.

### Stream 1: AGORA (episodic, per-citizen)

This is the generative-agents formula from the Stanford paper (Park et al., 2023). Each citizen has a `MemoryStream` of timestamped observations. When a query arrives, every memory gets scored:

```python
score = w_rel * relevance + w_rec * recency + w_imp * importance
```

- **relevance**: cosine similarity of the memory embedding to the query embedding, clamped to [0, 1]
- **recency**: exponential decay over ticks since the memory was last accessed -- `exp(-decay * age)`
- **importance**: a 1-10 poignancy score (assigned by the LLM or rules), normalized to [0, 1]

Retrieving a memory updates its `last_access_tick`. This means memories that keep getting surfaced stay fresh in the retrieval pool, which is a nice property: salient memories about an ongoing crisis persist.

```python
def _recency(self, mem: Memory, now: int) -> float:
    age = max(0, now - mem.last_access_tick)
    return math.exp(-self.weights.decay * age)

def retrieve(self, now, *, query_embedding=None, k=5, refresh=True):
    sims = self._vectors.similarities(query_embedding) if query_embedding else {}
    scored = []
    for mem in self.memories.values():
        relevance = max(0.0, sims.get(mem.id, 0.0))
        recency = self._recency(mem, now)
        importance = mem.importance / 10.0
        score = w.relevance * relevance + w.recency * recency + w.importance * importance
        scored.append(ScoredMemory(mem, score, relevance, recency, importance))
    scored.sort(key=lambda s: s.score, reverse=True)
    if refresh:
        for s in scored[:k]:
            s.memory.last_access_tick = now
    return scored[:k]
```

This is solid on its own. But it still ranks purely by how similar or recent a memory is. It doesn't know anything about causality.

### Stream 2: PANTHEON (causal, society-wide)

A NetworkX directed graph tracks what led to what at civilizational scale:

```
drought (tick 20) -> emergency rationing (tick 25) -> black-market spike (tick 30) -> civil unrest (tick 45) -> riots (tick 60)
```

Nodes are events: crises, decisions, policy outcomes. Directed edges encode causal precedence. Edge weights represent causal strength (0 to 1).

When a new crisis fires, TCMF does a bounded BFS backward from the crisis node to find its causal ancestors:

```python
def predecessors(self, event_id: str, max_depth: int = 4) -> dict[str, int]:
    visited: dict[str, int] = {}
    queue: list[tuple[str, int]] = [(event_id, 0)]
    while queue:
        node, depth = queue.pop(0)
        for pred in self._g.predecessors(node):
            new_depth = depth + 1
            if pred not in visited and new_depth <= max_depth:
                visited[pred] = new_depth
                queue.append((pred, new_depth))
    return visited  # {ancestor_id: depth_from_crisis}
```

Depth 1 is a direct cause. Depth 4 is four hops back. The result is a map of every causal ancestor within the lookback window.

---

## The fusion formula

For each citizen memory `m` scored against crisis query `q`:

```
tcmf_score(m) = episodic_score(m, q) x (1 + lambda x causal_boost(m))
```

`causal_boost(m)` is where the two streams connect. For each causal ancestor in the graph, TCMF computes the cosine similarity between the memory's embedding and the ancestor's embedding. If that similarity clears a threshold (default: 0.45), the memory gets a depth-weighted boost:

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
            # depth 1 (direct cause) gets boost 1.0; deeper ancestors get less
            normalized = 1.0 - (depth - 1) / max(max_depth, 1)
            best = max(best, sim * normalized)
    return best
```

The intuition: a citizen who was personally present at the *root cause* of the current crisis outranks one who only heard about it later, even if the second citizen's memory text reads more like the crisis description.

---

## Concrete example

Crisis: "Plague outbreak in the market district"

**Pure semantic RAG would surface:**
- "Merchants reported strange symptoms near the well" -- high similarity to "plague outbreak"
- "Children are sick, clinics are full" -- high similarity
- "City refused to fund quarantine infrastructure two weeks ago" -- low similarity, ranks low

**TCMF, assuming the quarantine refusal is a causal ancestor of the outbreak:**
- "City refused to fund quarantine infrastructure two weeks ago" -- gets causal boost, ranks up
- "Merchants reported strange symptoms near the well" -- ranks on its own merit
- "Children are sick, clinics are full" -- same

The council's context now includes the *reason* the plague spread as fast as it did, not just descriptions of the symptoms. That changes the deliberation. A council that knows it's dealing with a self-inflicted infrastructure failure will recommend different policy than one that thinks this is a random outbreak.

---

## What the council context block looks like

At the end of retrieval, TCMF composes a structured context block that goes directly into the council's prompt:

```
CRISIS: Plague outbreak in the market district

CITIZEN MEMORY EVIDENCE:
  - [Mayor Adisa] City refused to fund quarantine infrastructure two weeks ago (importance=8)
  - [Dr. Priya] Patients with hemorrhagic fever appearing at the clinic (importance=9)
  - [Merchant Reza] Trade routes already disrupted, suppliers pulling back (importance=6)

CAUSAL CHAIN (temporal-causal precedents):
  [tick 60] Infrastructure budget cuts passed by Senate
  [tick 65] Quarantine proposal rejected in emergency session
  [tick 72] First cases reported in the eastern ward
```

The LLM gets two things: ranked citizen memory evidence, and an explicit causal chain showing what led here. It can reason about both rather than treating the context as a flat bag of similar sentences.

---

## The full pipeline

```python
async def retrieve(self, question, citizens, tick, institution_id,
                   crisis_event_id=None, k=12, router=None) -> TCMFContext:

    # 1. Embed the crisis question (optional -- gracefully falls back without it)
    q_embedding = (await router.embed([question]))[0] if router else None

    # 2. BFS backward from the crisis node
    ancestors = self.graph.predecessors(crisis_event_id, max_depth=4) if crisis_event_id else {}

    # Also pull recent institution-scoped events as weak ancestors (depth=3 as fallback)
    for ev in self.graph.events_for_institution(institution_id)[-20:]:
        if ev["id"] not in ancestors:
            ancestors[ev["id"]] = 3

    # 3. Collect and score episodic memories from all citizens
    raw = []
    for cid, citizen in citizens.items():
        scored = citizen.memory.retrieve(tick, query_embedding=q_embedding, k=8, refresh=False)
        raw.extend((cid, sm) for sm in scored)

    # 4. Apply causal boost and re-rank
    max_depth = max(ancestors.values(), default=1) or 1
    fused = []
    for cid, sm in raw:
        boost = self._causal_boost_for_memory(sm.memory, ancestors, max_depth)
        score = sm.score * (1.0 + self.causal_boost * boost)
        fused.append((cid, sm.memory, score))

    fused.sort(key=lambda t: t[2], reverse=True)

    # 5. Deduplicate by memory id and take top-k
    seen, top = set(), []
    for cid, mem, sc in fused:
        if mem.id not in seen:
            seen.add(mem.id)
            top.append((cid, mem, sc))
        if len(top) >= k:
            break

    # 6. Compose context block
    ...
```

---

## The implementation stack

- **NetworkX DiGraph** for the causal graph. Free BFS/DFS, edge weights, Python-native. No graph database needed at our scale.
- **NumPy vector store** (no Chroma, no Pinecone). At ~10 agents with a few hundred memories each, brute-force cosine over an in-memory matrix is exact and fast. One matrix-vector dot per query: `sims = matrix @ q_normalized`. I wrote 60 lines instead of importing a database, and I have full control over the scoring.
- **Asyncio throughout**. Embedding calls are async, retrieval is non-blocking, the council orchestration uses `await`.
- **Embeddings are optional**. When no embedding is available, relevance scores to 0 and the formula falls back to recency + importance. The system runs in tests and in embedding-free mode without breaking.

---

## The honest tradeoffs

**What TCMF gains over plain episodic RAG:**

- Surfaces root-cause memories that similarity alone misses
- The causal chain summary gives the LLM explicit historical structure to reason about
- Deduplication prevents a single shared memory from dominating because multiple citizens happen to hold it
- Graceful degradation at every level: no embeddings, no causal graph, no crisis event ID -- each missing piece degrades cleanly rather than crashing

**What TCMF costs:**

The causal graph has to be maintained. Events need to be logged, links need to be drawn. In CivilizationOS, crisis events and council decisions are added automatically as the simulation runs. In a real system, you'd need an event-logging pipeline and something to decide what caused what.

`auto_link_predecessors()` handles cases where explicit causal links aren't known -- it infers weak links using temporal proximity plus semantic similarity:

```python
def auto_link_predecessors(self, new_event_id, window_ticks=48, semantic_threshold=0.5):
    new_data = self._g.nodes[new_event_id]
    new_tick = new_data["tick"]
    new_emb = new_data.get("embedding")
    for nid, data in self._g.nodes(data=True):
        age = new_tick - data["tick"]
        if age <= 0 or age > window_ticks:
            continue
        t_weight = math.exp(-0.05 * age)
        s_weight = max(0.0, _cosine(new_emb, data["embedding"])) if new_emb and data.get("embedding") else 0.0
        combined = 0.5 * t_weight + 0.5 * s_weight
        if combined >= 0.3:
            self._g.add_edge(nid, new_event_id, weight=round(combined, 3))
```

But inferred causality is noisy. "Things that happened around the same time and sound related" is a proxy for "things that caused each other." It's useful for filling a sparse graph, not a replacement for explicit causal modeling.

There are also three tunable parameters: `causal_boost` (lambda), `causal_sim_threshold`, and `max_depth`. Getting these wrong either swamps the episodic signal or makes the causal boost irrelevant. The defaults (lambda=0.6, threshold=0.45, depth=4) came from running the test suite and checking whether causally-boosted memories ranked above unrelated ones -- not from any rigorous sweep.

And at production scale, BFS over a dense causal graph adds latency. At CivilizationOS's current scale it's trivially fast. At scale it becomes a real concern.

**When to use TCMF vs. plain episodic RAG:**

Use TCMF when your agent operates in a causally structured environment -- one where past events produce downstream effects and those chains matter for decision-making. If you're building a support chatbot over a static knowledge base, standard RAG is the right tool. If you're building agents that need to reason about *why* things happened, TCMF is one way to get that context into the prompt.

---

## What I'd change in v2

**Use edge weights in the boost.** Right now `link()` stores a weight but `_causal_boost_for_memory` ignores it. A strong direct cause (weight=1.0) should contribute more than a weak inferred link (weight=0.3). The fix is a one-liner: multiply `sim * normalized` by `ev_weight`.

**Add reflection-generated memories.** The Stanford paper's agents periodically "reflect" on their memories and generate higher-level observations: "I've seen three crises in the health sector this month" rather than individual raw events. Adding reflection to CivilizationOS would let councils reason about patterns over time, not just individual incidents.

**Cross-institution causal links.** Right now the institution-scoped fallback adds recent events at a fixed weak depth. A proper multi-institution causal graph would model how a Treasury budget decision cascades into a Military readiness crisis. The graph structure supports it -- the retrieval just doesn't use cross-institution ancestors yet.

---

## Source

The implementation lives in `CivilizationOS/api/memory/`. The three core files:

- `tcmf.py` -- `TCMFRetriever` and `TCMFContext`
- `causal_graph.py` -- `CausalGraph` with BFS traversal and auto-linking
- `stream.py` -- `MemoryStream` with the episodic scoring formula

If you're building multi-agent simulations or agentic systems where decisions have downstream effects, the core idea here is worth considering: semantic similarity and causal relevance are not the same thing, and for an agent making decisions under pressure, the difference matters.
