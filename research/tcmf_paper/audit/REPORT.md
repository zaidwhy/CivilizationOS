# TCMF adversarial audit: report

2026-11-13. Everything here traces to a file in `results/`; the commands are in `REPRODUCE.md`,
the protocol and its deviations in `PREREG.md`, both independent reviews in `REVIEW_LOG.md`.

**Addendum, same day:** the retriever's defaults were changed because of this audit. Everything
below describes the retriever as audited (commit `70a227d`); the change and its measured effect
are in "Addendum: the fix" near the end.

Two names are used throughout. **Shipped** is the production class
`api.memory.tcmf.TCMFRetriever`, called unmodified with its defaults. **Paper configuration**
is the same scoring without the weak-ancestor rule, which is what `tcmfbench` evaluates; it is
my re-implementation with that rule switched off (and, on real text, the paper's 0.60
threshold), because the production class has no switch for it.

## Verdict

**The idea survives. The architecture around it does not earn its parts, and the retriever
that ships is not the one the benchmark measures.**

1. **A correct causal graph is worth a great deal.** On a perfect graph the paper
   configuration puts a root-cause memory in the top 5 on 500 of 500 synthetic scenarios, and
   lifts an LLM reader's root-cause accuracy from 0.28 (vector retrieval) to 0.83, with decoy
   causes present in memory. Three reader and encoder pairings agree (0.80 to 0.83 against
   0.23 to 0.31).
2. **The fusion is not what delivers it.** A reader of the same graph with no fusion
   arithmetic (no weight, no threshold, no normalization, no episodic term) puts the same mix
   of root, chain and symptom memories in its top 5 on 500 of 500 synthetic scenarios and
   gives the same decisions within noise. The graph's chain text with zero retrieved memories
   matches or exceeds both. Once the weight lambda is above about 2, no component except the
   depth weight changes where the root lands on a clean graph.
3. **The shipped retriever has a rule the benchmark never exercises, and it reverses the
   result.** With the production encoder and a perfect graph, the shipped retriever scores
   0.02 on decisions, below the no-memory floor of 0.25, with both readers.
4. **The shipped graph builder cannot find the causes the paper is about.** It links only
   events inside a 48-tick window, so a cause older than that is unreachable by construction;
   inside the window it links by similarity, which is the signal the paper says fails.
5. **A graph that confidently names the wrong cause is worse than no memory**: 0.06 to 0.18
   against 0.25.

So TCMF is not useless, but the honest description is "retrieval is as good as the causal graph
you hand it", and this audit found no evidence that the deployed linker produces that graph in
the paper's regime (an old cause that looks unlike the crisis). The work that would make the
architecture real is graph construction, not fusion.

What the audit does **not** overturn: the existing paper's claims are about how two fusion
operators behave on a given graph, and it already says graph errors cost more than operator
choice. Nothing here contradicts that. Three things in it should be checked against these
results before submission; see "For the paper".

## The registered hypotheses, as registered

| | Hypothesis | Outcome on the registered metric (root in top 5) |
|---|---|---|
| H1 | With a perfect graph, fusion adds nothing over a fusion-free graph reader | **Supported** for chains that fit the cutoff (identical on 500 of 500). **Refuted at depth 4**, where the depth weight wins by 0.24. |
| H2 | On the production linker's graph, TCMF does not beat vector | **Refuted** (0.44 against 0.00), but vector is 0 by construction in that world; see "What I got wrong". |
| H3 | Unrelated events in the graph lower the shipped retriever's result | **Supported** at top 5 (drops of 1.00, 1.00 and 0.38 at depths 1 to 3 with 6 other events). At top 8, which is what production shows, there is **no drop** with 6 other events; the drop appears from 12. |
| H4 | TCMF's margin over vector turns negative on a noisy graph as the cause grows more similar to the crisis | **Refuted** as registered (margins 0.17 to 0.69, Holm p = 0.002). The repaired version (`P2_`, two symptoms so vector is not floored) shows the margin shrinking but staying positive. |
| H5 | The graph's chain text alone matches the shipped retriever's memories on decisions | **Supported**, and far beyond the margin: the shipped retriever is 0.52 to 0.96 below chain text in all six cells. |
| H6 | Removing recency does not lower root retrieval | **Supported** at every cutoff. |

## What I got wrong on the way

- **H2 and H4 came out against me**, and both were badly posed: vector retrieval scores
  exactly 0 by construction in my default world (six symptom memories, top 5), so a margin
  over it says little in either direction.
- **My top-5 cutoff exaggerated two results.** I first read "root never retrieved" where the
  truth was "root at rank 7"; production shows 8. The first reviewer caught it.
- **My recency result was mostly an artifact** (+0.13 shrank to +0.02 once cause and
  unrelated-event ages were matched).
- **I wired H5's confirmatory arm to my re-implementation**, against my own pre-registration.
  Corrected before any Tier B number was read.
- **My wrong-graph arm kept the true mechanism event**, so it was only half wrong. Fixed.
- **My noise model only ever made unrelated events shallow**, which a root-favouring weight
  forgives; that flattered TCMF. A deep-false-edge cell was added.
- **I did not report my own failed control as failed** until the reviewer pointed at it.
- **I claimed equivalence from point-null tests.** Verdicts now compare intervals with the
  registered margin.
- **I called the arm "deployed"** when it is the production class on memories I generated.
- **The production prompt arm ran over budget and logged nothing about what it showed.** Fixed.
- **Two of my baselines were poor.** My PageRank baseline scores 0 everywhere and is cited
  nowhere. My graph-free two-hop retriever did not replicate across encoders.
- **I truncated the second reader's answers** (4 output tokens) and nearly reported a harness
  bug as a failed replication.

## The setup in one paragraph

Two tiers. **Tier A** is synthetic and offline: my own generator, in which a latent causal chain
defines the relevant memories and the graph a retriever sees is a separate object that can be
perfect, noisy, wrong, or built by the production linker. 500 scenarios per cell, paired across
methods, 126 cells. **Tier B** is an end task: 128 templated incidents in 8 domains with real
text and real embeddings; each crisis has four council decisions on record, all four with
witness memories, exactly one of which caused it; a local LLM picks the root cause from the
four. Retrieval arms show the reader 5 memories; the chain-text arm is shorter (about 168
prompt tokens against 220), the gold arm shows 2 or 3 memories, and the production prompt block
is larger by design (8 memories plus chain, about 495 tokens) and is labelled wherever it
appears. Readers: qwen2.5 3B and llama3.2 3B. Encoders: nomic-embed-text (the system's) and
all-MiniLM. Three of the four pairings were run (llama with nomic only). The ablation
re-implementation is held to ranking parity with the production class by a test, on the default
path and on the path with the weak-ancestor rule off. Parity is exact except for the order of
two memories whose scores are exactly equal (production breaks such ties by citizen, mine by
index): 3 of 600 rankings differed that way, none inside the top 12.

## Finding 1: with a correct graph, the fusion adds nothing a plain graph reader lacks

Synthetic, perfect chain-only graph, cause orthogonal to the crisis (the paper's premise),
n = 500. `graph_union` alternates two lists: memories nearest the crisis's ancestors, and
memories nearest the query.

| method | root in top 5 | root in top 8 | root MRR | symptom recall@5 |
|---|---|---|---|---|
| random (control) | 0.15 | | | |
| vector | 0.00 | 0.07 | 0.06 | 1.00 |
| generative-agents score | 0.00 | | | 1.00 |
| sliding window (newest first) | 0.00 | | | 0.91 |
| `graph_union` (no fusion) | 1.00 | 1.00 | 0.53 | 0.40 |
| TCMF, paper configuration | 1.00 | 1.00 | 1.00 | 0.40 |
| oracle (control) | 1.00 | | | |

The two graph readers agree on every per-scenario metric on all 500 scenarios (ranked lists
were not stored in Tier A, so this is the same composition, not proven the same items). TCMF
ranks the root first (MRR 1.00 against 0.53) because of its depth weight. That is a real gain
and it presumes the question is always about the deepest ancestor.

Ablations on this condition (root in top 5):

| removed or changed | result |
|---|---|
| similarity threshold (0, or 0.60) | 1.00, no change |
| min-max normalization | 1.00, no change (symptom recall moves 0.40 to 0.57) |
| recency, importance, or relevance term | 1.00, no change |
| the whole episodic term | 1.00, no change (symptom recall falls to 0.08) |
| weight lambda: 2, 4, 8, 16 | 1.00 |
| weight lambda: 1 / 0.5 / 0 | 0.96 / 0.00 / 0.00 |
| multiplicative operator at lambda 16 | 1.00 |
| depth weight made uniform | 1.00 (root MRR 1.00 to 0.44) |

Once lambda clears its bound the score is a sort key: graph-matched memories first, everything
else after. The episodic term decides only what fills the remaining slots.

Chain depth, perfect chain-only graph (root in top 5):

| chain depth | `graph_union` | paper configuration | shipped |
|---|---|---|---|
| 1 to 3 | 1.00 | 1.00 | 1.00 |
| 4 | 0.76 | 1.00 | 1.00 |
| 5 | 0.61 | **0.00** | 1.00 |
| 6 | 0.49 | **0.00** | 1.00 |

At depth 4 the depth weight beats the fusion-free reader by 0.24; that refutes my H1 there.
Beyond four hops the paper configuration scores 0 at every cutoff (0.00 to 0.01 even at top
12), because the ancestor walk stops at `max_depth = 4`, and the fusion-free reader wins. The
shipped class reaches 1.00 only because its weak-ancestor rule re-adds the chain events, and
only on a chain-only graph: with six other events logged it scores 0.23 and 0.20 at depths 5
and 6.

End task, perfect graph (accuracy, no link evidence / link evidence present):

| arm | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| no memory (floor) | 0.25 / 0.24 | 0.25 / 0.24 | 0.24 / 0.25 |
| vector | 0.28 / 0.59 | 0.31 / 0.68 | 0.23 / 0.46 |
| TCMF, paper configuration | 0.83 / 0.91 | 0.80 / 0.92 | 0.80 / 0.87 |
| `graph_union` (no fusion) | 0.80 / 0.95 | 0.82 / 0.91 | 0.77 / 0.94 |
| chain text only, **no memories** | 0.95 / 0.96 | 0.95 / 0.96 | 0.98 / 0.98 |
| gold memories (ceiling) | 0.91 / 0.98 | 0.91 / 0.98 | 0.88 / 0.95 |

TCMF minus `graph_union` is between -0.07 and +0.03 in all six cells. With 8 domains that is
"no detectable difference", not proven equivalence; in Tier B the two readers show the same
five memories in only 24 to 75 of 256 scenarios, so they are different retrievers that lead to
the same decisions. Chain text matches or exceeds the paper configuration in every cell (by
0.04 to 0.18); that margin is resolved in about half the cells. The chain-text arm does well
for a plain reason: with a correct graph, the answer is in the graph.

One disclosure against the paper configuration's MiniLM column: it uses the 0.60 threshold
tuned for nomic, and under MiniLM that drops the root witness from its top 5 in 19% of
scenarios. A threshold tuned for MiniLM would likely do better.

## Finding 2: the shipped weak-ancestor rule outranks true causes with unrelated events

`TCMFRetriever.retrieve` adds the institution's last 20 events as "weak ancestors" at depth 3
and weights every ancestor by `depth / deepest`. In a graph that holds other events of the
institution, an event with **no** causal link to the crisis gets depth 3 while the crisis's
direct cause gets depth 1. The unlinked event wins.

`tcmfbench` never runs this rule on a graph where it could add anything. Its chain-only tiers
make it a no-op, and the two tiers that do add unrelated events (N16 multi-crisis, N29 clutter)
compute the clean ancestor map (`clean=True`). The docstring in `methods.py` that says the
fallback "only re-adds chain events" on every tier is stale for those two.

Synthetic, **perfect** graph, chain depth 3, as the institution's log grows (root in top
5 / 8 / 12; production asks for 12 and shows the council 8):

| other events logged | shipped | shipped, shuffled graph (control) | edge-free event-log baseline | paper configuration |
|---|---|---|---|---|
| 0 | 1.00 / 1.00 / 1.00 | | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| 6 | 0.62 / 1.00 / 1.00 | 0.55 / 1.00 / 1.00 | 0.58 / 0.87 / 1.00 | 1.00 / 1.00 / 1.00 |
| 12 | 0.18 / 0.46 / 0.87 | 0.14 / 0.43 / 0.86 | 0.38 / 0.54 / 0.80 | 1.00 / 1.00 / 1.00 |
| 18 | 0.08 / 0.25 / 0.49 | 0.06 / 0.20 / 0.40 | 0.25 / 0.39 / 0.59 | 1.00 / 1.00 / 1.00 |
| 30 | 0.01 / 0.07 / 0.25 | | 0.17 / 0.25 / 0.37 | 1.00 / 1.00 / 1.00 |
| 50 | 0.00 / 0.01 / 0.07 | | 0.07 / 0.12 / 0.21 | 1.00 / 1.00 / 1.00 |

Three readings. With a perfect graph the shipped retriever loses the root as the log grows,
while the same scoring without the rule stays at 1.00. Its results with the right graph and
with a deliberately wrong one are nearly the same, so **the pre-registered negative control
failed for the shipped retriever**: its edges are not what drives its output. And it does worse
than a baseline that ignores edges entirely, from 12 events at top 5 and top 8 and from 18 at
top 12.

On real text with the production encoder the damage arrives at once, because the 0.45
similarity threshold separates nothing: with `nomic-embed-text`, 84% of all memories exceed
0.45 against some logged event (15% with MiniLM). Almost every memory is "boosted", and the
three unrelated decisions carry the top weight. End task, perfect graph:

| arm | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| no memory (floor) | 0.25 / 0.24 | 0.25 / 0.24 | 0.24 / 0.25 |
| vector | 0.28 / 0.59 | 0.31 / 0.68 | 0.23 / 0.46 |
| shipped, 5 memories | **0.02 / 0.06** | 0.24 / 0.45 | **0.02 / 0.12** |
| shipped, production prompt block (8 memories + chain; over budget) | 0.15 / 0.29 | 0.28 / 0.44 | 0.19 / 0.31 |
| chain text only | 0.95 / 0.96 | 0.95 / 0.96 | 0.98 / 0.98 |

The confirmatory test (H5, shipped memories against bare chain text) is -0.52 to -0.96 in all
six cells, Holm p = 0.016 in each file, the smallest value 8 domains allow. With nomic the root
witness is in the shipped top 5 in 1 of 256 scenarios. With MiniLM it is there in 91%, and
accuracy still sits at the floor (0.24), because all four decisions' witnesses are shown and
nothing tells them apart. The production prompt block lists the institution's events (the
eight oldest, which is all of them here) under the heading "CAUSAL CHAIN (temporal-causal
precedents)", true cause and unrelated decisions alike.

The rule is not only harmful, and this should be said plainly:

- **It rescues missing edges.** With 25% to 75% of true edges dropped and a 6-event log, the
  shipped retriever keeps the root in the top 8 on 0.87 to 0.96 of scenarios (top 5: 0.36 to
  0.52), while the paper configuration falls to 0.42, 0.11 and 0.02, about the probability
  that the root is still reachable. On the mixed-noise cell (30% dropped, two false edges) it
  beats the paper configuration and the fusion-free reader at top 5 as well (0.70 against 0.34
  and 0.23).
- **It gets better as false edges are added** (0.62 to 0.98 with four), because a falsely
  linked event receives its shallow depth and drops below the unlinked ones. That is the same
  inversion working by accident.

So the rule trades precision on a good graph for recall on a bad one, and the trade turns
against it as the log grows.

## Finding 3: the production linker cannot produce the graph the benchmark assumes

`api/sim/engine.py` creates a crisis's incoming edges from past events only with
`CausalGraph.auto_link_predecessors` (a secondary crisis also gets one explicit edge from its
primary). That function links events inside a 48-tick window, scored by time proximity plus
embedding similarity. The benchmark links true causes by hand.

A cause older than 48 ticks is therefore unreachable **by construction**. In the paper's regime
as I built it (cause 60 to 150 ticks old) the root was linked in 0 of 500 synthetic and 0 of
128 text scenarios; that is a restatement of the window, not a measurement of quality. The
measurement is what happens inside the window (synthetic, n = 500):

| regime | true ancestors found | precision | true root linked |
|---|---|---|---|
| cause old and unlike the crisis: the paper's premise | 0.07 | 0.31 | 0 of 500 |
| cause old, moderately similar (rho 0.5) | 0.25 | 0.64 | 0 of 500 |
| cause recent (5 to 40 ticks), unlike the crisis | 0.44 | 0.74 | 92 of 500 |
| cause recent and moderately similar | 0.97 | 0.89 | 461 of 500 |

The linker works when the cause is recent and looks like the crisis, which is when similarity
search needs the least help; in that cell the paper configuration reaches 0.92 on the linker's
own graph. In the text tier the linker attached 27% of the unrelated decisions to the crisis
with nomic and 6% with MiniLM.

**The shipped system end to end.** On its own linker's graph, with nomic, the shipped retriever
puts the root witness in the top 5 in 89% of text scenarios, against under 1% on a perfect
graph. The true root is never linked, so it stays a weak ancestor at depth 3, the top weight;
recent unrelated decisions do get linked, at depth 1, the bottom weight. With nomic the
retriever does better with a bad graph than a good one because "unlinked" outranks "linked".
(With MiniLM the two graphs give the same 91%.) Against vector retrieval, when no memory links
cause to crisis:

| arm on the production linker's graph | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| vector | 0.28 | 0.31 | 0.23 |
| shipped, 5 memories (budget-matched) | 0.34 | 0.37 | 0.36 |
| shipped, production prompt block (8 memories + chain) | 0.47 | 0.45 | 0.42 |

The budget-matched gain is +0.06, +0.06 and +0.13, resolved only with llama. The larger gain
of +0.13 to +0.20 belongs to the production block, which shows the reader more. All of these
comparisons are exploratory and unadjusted. With link evidence present the gain is gone in
every pairing (-0.11 to +0.09). So my H2 was wrong, the shipped system does help somewhat in
the paper's regime, and the help comes from an accident of the weighting that depends on the
true cause being old and on few events being logged (Finding 2's table is the same retriever
with more events).

**Found by reading the engine, not measured:**

- Crisis observations are written through `_remember` (`engine.py:448-449, 481-483`), which
  stores no embedding, and `_causal_boost_for_memory` returns 0 for a memory with none. In the
  running simulator the citizens' memories of a crisis cannot receive a causal boost.
- With `use_llm=False`, which the project's deploy notes say the hosted demo uses,
  `_remember_async` stores no embedding either (`engine.py:453`), the crisis event gets none
  (`engine.py:498-502`) and no router is passed to the retriever (`engine.py:549`). In that
  mode every memory's causal boost and relevance are 0 and the ranking is recency plus
  importance. The linker then scores on time alone, which shrinks its effective window to
  about 10 ticks.

I did not replay a live engine run to confirm either.

## Finding 4: everything rides on graph quality, and a wrong graph misleads

The wrong graph here is a coherent one: it names one of the three unrelated decisions as the
root and that decision's own would-be mechanism as the middle step.

| arm | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| no memory (floor) | 0.25 / 0.24 | 0.25 / 0.24 | 0.24 / 0.25 |
| paper configuration, wrong graph | 0.06 / 0.09 | 0.08 / 0.18 | 0.10 / 0.12 |
| chain text, wrong graph | 0.03 / 0.02 | 0.03 / 0.02 | 0.01 / 0.01 |
| paper configuration, production linker's graph | 0.22 / 0.33 | 0.23 / 0.41 | 0.27 / 0.35 |

Accuracy falls 0.06 to 0.24 below having no memory at all. Chain text is the best arm on a
correct graph and the most damaging on a wrong one. The paper configuration on the production
linker's graph sits at the floor when there is no link evidence. In Tier A, false edges that
make an unrelated event the deepest node leave the root in the top 5 but halve its rank (MRR
1.00 to 0.51 with four such edges), since the depth weight now favours the impostor.

## Finding 5: the "temporal" part contributes nothing measurable

The only temporal signal in the score is the recency term inside the episodic score. Removing
it never lowered root-in-top-5, 8 or 12 in any cell. With cause and unrelated-event ages
matched, removing it changes root-in-top-5 by +0.02 and root-in-top-8 by 0 (root MRR moves by
-0.02). Graph depth is a count of hops, not time. The boost depends on the crisis id, not on
what is asked: the paper configuration keeps 2 of 5 slots for crisis symptoms (symptom recall
0.40); the shipped retriever keeps none (0.00) once five event memories exist, so a question
about the crisis's present state gets no memory of it.

## How the simpler memories did

| memory | finds a far root cause? (Tier A, top 5) | end task, no link / link (qwen + nomic) | cost |
|---|---|---|---|
| sliding window | no (0.00) | 0.27 / 0.60 | none |
| rolling LLM summary | not measured as a ranking | 0.27 / 0.47 | 2 LLM calls per 32 memories at write time, about 2 s each on a 4 GB GPU, 350 tokens in, 117 out |
| vector retrieval | no (0.00) | 0.28 / 0.59 | 0.9 ms at 5,000 memories |
| generative-agents score | no (0.00) | 0.28 / 0.36 | same order as vector |
| graph reader, no fusion | yes, given a correct graph | 0.80 / 0.95 | 3.6 to 4.7 ms at 5,000 memories |
| chain text only | yes, given a correct graph | 0.95 / 0.96 | 168 prompt tokens against about 220 |
| TCMF, paper configuration | yes, given a correct graph | 0.83 / 0.91 | about 2.6 ms if vectorized (timed on the shipped scoring) |
| TCMF, shipped | not reliably (Findings 2, 3) | 0.02 / 0.06 on a perfect graph | **1,131 ms** at 5,000 memories and 21 events; prompt block about 495 tokens |

Without a graph nothing finds a far cause; that part of the paper's premise holds. When any
memory links the mechanism to the crisis, plain vector retrieval and even a sliding window
recover much of the answer (0.46 to 0.68), and the graph's advantage narrows from about +0.55
to about +0.3. The rolling summary trails vector once evidence exists (0.47 against 0.59 with
qwen, 0.27 against 0.46 with llama), because early records are written out of the running
summary. The shipped retriever's cost is implementation, not algorithm: it computes one
Python-level cosine per (memory, ancestor) pair; the identical ranking as two matrix products
is about 440 times faster.

## What the evidence supports doing

1. **Remove the weak-ancestor rule, or cap its weight below every true ancestor.** That
   restores 1.00 on a correct graph at every log size tested. It also removes the rule's rescue
   of missing edges, so if a fallback is wanted, make it explicit and separate (the event-log
   baseline), not a depth.
2. **Stop calling the score a fusion.** At the shipped weight it is "graph-matched memories
   first". A two-list reader reaches the same decisions with no parameters.
3. **Pass the chain as text when the graph is trusted.** It matched or beat every retrieval
   arm at fewer tokens. It is also the arm that does most harm when the graph is wrong, so it
   raises the stakes on graph quality.
4. **Keep the depth weight; raise or remove `max_depth`.** The depth weight is the one
   component that earned a result, and the cap silently drops roots beyond four hops.
5. **Set the similarity threshold per encoder, in the shipped default.** 0.45 is inert under
   the encoder the system uses.
6. **Embed the memories the boost is supposed to reach** (`_remember`, and the `use_llm=False`
   path).
7. **Put the research effort into the graph.** Every result above is a function of graph
   quality. The linker is the weak component and the benchmark never tests it.

A graph-free multi-hop retriever was my proposed alternative. It beat vector with nomic (0.38
against 0.28 with qwen, 0.32 against 0.23 with llama; with link evidence 0.73 against 0.59 and
0.70 against 0.46) and not with MiniLM (0.27 against 0.31, 0.66 against 0.68). **Not supported
as a general result.**

## Addendum: the fix

Zaid asked for the best change to be made. Three defaults of `TCMFRetriever` changed
(`api/memory/tcmf.py`); nothing else in the system did.

| default | audited | now | why |
|---|---|---|---|
| `weak_ancestor_depth` | 3 | 0.5 | an unlinked event must sit below a direct cause (depth 1), not above it |
| `causal_sim_threshold` | 0.45 | 0.60 | the value tuned for nomic-embed-text, the encoder the system runs |
| `max_depth` | 4 | 8 | roots more than four hops back were never reached |

The rule was kept, not deleted, because deleting it also removes the rescue of missing edges
(Finding 2). `tcmfbench` now pins the audited values, so every committed benchmark number
regenerates unchanged; that was checked by regenerating `results_main` and `results_mixed`
before and after.

Synthetic tier, root in top 5 / 8 / 12, n = 500 (`F1_after_fix`):

| condition | audited | now | paper configuration |
|---|---|---|---|
| perfect graph, 6 other events | 0.62 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| perfect graph, 18 other events | 0.08 / 0.25 / 0.49 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| perfect graph, 50 other events | 0.00 / 0.01 / 0.07 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| perfect graph, chain depth 1 or 2 | 0.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| perfect graph, chain depth 6 | 0.20 / 0.62 / 1.00 | 1.00 / 1.00 / 1.00 | 0.00 / 0.00 / 0.00 |
| shuffled graph (control), 6 other events | 0.55 / 1.00 / 1.00 | 0.00 / 0.00 / 0.19 | 0.00 / 0.00 / 0.01 |
| 25% of edges dropped, 6 other events | 0.52 / 0.96 / 1.00 | 0.59 / 0.88 / 0.99 | 0.42 / 0.42 / 0.45 |
| 50% of edges dropped, 6 other events | 0.44 / 0.92 / 1.00 | 0.38 / 0.84 / 1.00 | 0.11 / 0.11 / 0.17 |
| no edges at all, 6 other events | 0.33 / 0.82 / 1.00 | 0.33 / 0.82 / 1.00 | 0.00 / 0.00 / 0.08 |
| 30% dropped and 2 false edges, 6 other events | 0.70 / 0.99 / 1.00 | 0.46 / 0.81 / 0.96 | 0.34 / 0.34 / 0.36 |
| production linker, cause old and unlike the crisis, 6 other events | 0.47 / 0.92 / 1.00 | 0.31 / 0.78 / 0.96 | 0.00 / 0.00 / 0.08 |
| production linker, same, 18 other events | 0.12 / 0.28 / 0.48 | 0.02 / 0.10 / 0.23 | 0.00 / 0.00 / 0.00 |
| production linker, cause recent and similar | 0.02 / 0.49 / 0.92 | 0.96 / 1.00 / 1.00 | 0.93 / 0.98 / 1.00 |

The negative control now behaves: a wrong graph gives a wrong answer, so the edges are what
drive the output. On any graph whose edges are right the root is found, at every log size and
depth tested. Most of the missing-edge rescue survives. **What was lost** is the accident: where
the true cause is old and the production linker never links it, the audited version did better
(0.92 against 0.78 in the top 8 with a short log), because unlinked used to outrank linked.

End task, decision accuracy, no link evidence / link evidence present:

| arm | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| vector | 0.28 / 0.59 | 0.31 / 0.68 | 0.23 / 0.46 |
| **perfect graph**, 5 memories: audited | 0.02 / 0.05 | 0.24 / 0.45 | 0.02 / 0.12 |
| perfect graph, 5 memories: now | 0.76 / 0.82 | 0.51 / 0.55 | 0.66 / 0.73 |
| perfect graph, production prompt block: audited | 0.15 / 0.29 | 0.28 / 0.44 | 0.19 / 0.31 |
| perfect graph, production prompt block: now | 0.74 / 0.77 | 0.59 / 0.68 | 0.58 / 0.66 |
| **production linker's graph**, 5 memories: audited | 0.34 / 0.59 | 0.37 / 0.57 | 0.36 / 0.55 |
| production linker's graph, 5 memories: now | 0.28 / 0.48 | 0.26 / 0.33 | 0.41 / 0.48 |
| production linker's graph, production prompt block: audited | 0.47 / 0.56 | 0.45 / 0.63 | 0.42 / 0.46 |
| production linker's graph, production prompt block: now | 0.36 / 0.53 | 0.41 / 0.52 | 0.39 / 0.37 |

With a correct graph the retriever went from below the no-memory floor to 0.51 to 0.82. On the
production linker's graph, in scenarios built so that the linker can never reach the cause, it
is 0.03 to 0.11 lower end to end than the audited version and still 0.08 to 0.16 above vector
when no memory links cause to crisis. These comparisons are over 8 domains and are exploratory.
The MiniLM column runs the nomic threshold and is lower for that reason.

Why I judged this the right trade: in the running simulator the edges that exist are either
explicit (a crisis to its secondary crisis, a crisis to its verdict) or drawn by the linker
between recent, similar events. Those are the edges that are usually right, and the audited rule
ranked the events on them **below** unrelated ones. The regime where the audited version did
better is one the linker cannot serve at all; fixing that needs a better linker, not a weighting
that happens to favour whatever is unlinked.

**One change was tried and reverted.** I also narrowed the prompt's "CAUSAL CHAIN" text to the
events the graph actually links. Measured:

| production prompt block, now | qwen + nomic | qwen + MiniLM | llama + nomic |
|---|---|---|---|
| perfect graph, chain lists weak ancestors too (shipped) | 0.74 / 0.77 | 0.59 / 0.68 | 0.58 / 0.66 |
| perfect graph, chain narrowed to linked events | 0.98 / 0.99 | 0.95 / 0.99 | 0.79 / 0.79 |
| production linker's graph, chain lists weak ancestors too (shipped) | 0.36 / 0.53 | 0.41 / 0.52 | 0.39 / 0.37 |
| production linker's graph, chain narrowed to linked events | 0.21 / 0.36 | 0.37 / 0.45 | 0.18 / 0.24 |

Worth +0.13 to +0.36 on a correct graph and -0.04 to -0.21 on the production linker's, where it
falls below the no-memory floor with nomic: the heading asserts the linker's edges and the
reader believes them. It stays reverted until the linker can be trusted. This is Finding 4
again, and the clearest single number for where the next work should go.

Still open from "What the evidence supports doing": embedding the memories written through
`_remember` (item 6), and the linker (item 7). Items 1, 4 and 5 are done; items 2 and 3 are
descriptions and a prompt change that waits on the linker.

Verification of the change: `pytest api/tests` 83 passed (6 new; 4 of them fail on the audited
code), `pytest tcmfbench` 214 passed and 1 skipped, the audit's own suite 25 passed including
ranking parity with the retriever as it ships now, and 3,198 audited rows regenerated from the
changed code with 0 mismatches.

## For the paper

The three scope statements below were added to the Limitations sections of all three manuscript
versions on 2026-11-13 (private paper repository, commit `4fa92f6`); no result, table or claim
changed.

- The benchmark never runs the weak-ancestor rule where it can act. Any sentence that presents
  benchmark numbers as the behaviour of the deployed system needs that scope stated, or the
  rule removed from the system.
- The decision tier's decoy causes are "external shocks NOT in the record" (`decision.py`), so
  a reader can score by choosing the only option its context mentions. With decoys present in
  memory the direction holds (0.83 against 0.28), so this is a threat to disclose, not a
  reversal.
- "When the environment logs which events caused which" carries the whole result. The system's
  own environment does not log that; it infers links from time and similarity inside 48 ticks.
  The paper's LLM-built-graph section already points this way.

## What this audit is not

- Not a test of the paper's operator claims (additive against multiplicative on clean, leaky
  and cluttered graphs). I ran one multiplicative arm; it tied.
- Not evidence about causal graphs built by a strong LLM or by hand-written instrumentation.
  I tested perfect graphs, random corruption, one coherent wrong graph, and the production
  heuristic.
- Not a measurement of the live simulator. The production retriever was called on memories I
  generated; the engine's fixed importances and missing embeddings were read, not replayed.
- Not a result about real agent logs. Tier A's geometry and Tier B's text are mine. Every
  geometric assumption was swept, including the paper's own setting, but I wrote the incidents
  and I knew the hypotheses.
- Not a statement about readers larger than about 3 billion parameters.

## Limitations

- **Tier B has 8 independent domains.** Intervals are wide; the smallest attainable two-sided
  p is 0.008. Differences under about 0.15 are not resolved. Only H5 is corrected for multiple
  testing; every other Tier B comparison is exploratory.
- **Pre-registration is on my word.** `PREREG.md` was written before the first run, but the
  folder was committed once, after the results, so git history cannot show the order. Nine
  deviations are listed in it.
- **The reviewers were models.** The first reviewed the design and Tier A before Tier B had
  data; the second fact-checked this report against the result files and the source. Between
  them they changed a dozen statements here. Neither replaces a person who works on retrieval.
- **The paper configuration's numbers come from my re-implementation**, not from a production
  call, because production cannot switch the rule off. The parity test covers it.
- **Tier A intervals describe sampling noise only.** Many differences are identical on all 500
  seeds; the real uncertainty is in design constants, which is why the tables sweep them.
- **Replication is three pairings, not a full 2 x 2**, one summarizer wrote the summaries for
  both readers, and cost figures are wall clock on one laptop.

## Files

| Path | What |
|---|---|
| `PREREG.md` | hypotheses, controls, confounds, deviations |
| `REVIEW_LOG.md` | both reviews and what changed |
| `REPRODUCE.md` | exact commands; what is deterministic |
| `tcmfaudit/` | generator, graph builders, retrievers, runners, statistics |
| `tests/` | harness checks, including parity with the production retriever |
| `results/retrieval/*.jsonl.gz` | Tier A raw rows, one per (cell, seed, method) |
| `results/retrieval/SUMMARY.md`, `tests.json` | every cell; the registered tests |
| `results/decision/cache_*.jsonl.gz` | every model call with its verbatim output |
| `results/decision/SUMMARY_audited_70a227d.md`, `tests_audited_70a227d.json` | Tier B tables and tests for the retriever as audited |
| `results/decision/SUMMARY.md`, `tests.json` | Tier B regenerated from current code, with the after-fix arms |
| `results/cost.json` | query-time cost |
