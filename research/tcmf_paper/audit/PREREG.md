# Pre-registration: adversarial audit of TCMF

Written 2026-11-13, before any experiment in this folder was run. Edits after the first run are
listed at the bottom under "Deviations", never made silently.

## What is being tested

The claim under attack is the practical one: *TCMF (walk the causal graph back from the crisis,
boost memories near its ancestors, fuse with the episodic score) is a memory architecture that
earns its complexity.* The existing paper narrows itself to "when does the fusion operator
matter"; this audit asks the prior question of whether the architecture adds anything over
simpler ones once three advantages the existing benchmark hands it are removed.

Three advantages found by reading the code, before running anything:

1. **Gold is defined by the graph the retriever is given.** In `tcmfbench` the relevant memories
   are exactly the witnesses of the nodes the oracle graph reaches. Any method that reads the
   same graph gets the same answer; the fusion never has to earn it.
2. **The benchmark graph is not the deployed graph.** The deployed engine creates a crisis's
   incoming edges only with `CausalGraph.auto_link_predecessors` (time proximity plus embedding
   similarity, window 48 ticks). The benchmark never calls it; it links true causes by hand.
   The paper's premise (the cause is old and looks nothing like the crisis) is the case that
   rule cannot link.
3. **The benchmark graph contains only chain events.** The deployed retriever also adds the
   institution's last 20 events as "weak ancestors" at depth 3, and weights by
   `depth / max_depth_seen`. With no other events in the graph that branch is dead code in every
   existing result.

Also noted: the existing decision tier offers decoy causes that never appear in memory
(`decision.py`: "external shocks NOT in the record"), so a reader can score by picking the only
option the context mentions.

## Hypotheses (each written so it can fail)

Primary metric: `root_hit@5` (a root-cause witness is in the top 5). Secondary: causal
`recall@5` normalized by `min(5, gold)`, symptom `recall@5`. All comparisons are paired on the
same scenarios; 95% CIs are paired bootstrap; the confirmatory family H1-H6 is Holm-corrected.

| id | Hypothesis | TCMF is vindicated (my hypothesis is wrong) if |
|---|---|---|
| H1 | With a perfect graph, TCMF's fusion adds nothing over reading the same graph with no fusion: `graph_union` (round-robin of ancestor-similarity and query-similarity lists; no weight, threshold, depth weight or normalization) is within 0.05 of TCMF on root_hit@5. | TCMF beats `graph_union` by more than 0.05 with the CI excluding 0. |
| H2 | On the graph the deployed code builds (`auto_link_predecessors`), TCMF does not beat plain vector retrieval on root_hit@5 in the paper's own regime (cause semantically far, older than the link window). | TCMF on the deployed graph beats vector by more than 0.05, CI excluding 0. |
| H3 | When the institution has other, causally unrelated events in the graph, the deployed weak-ancestor rule lowers root_hit@5 relative to the same retriever on a chain-only graph, most at chain depth below 3. | No drop larger than 0.05 at any depth 1-3. |
| H4 | TCMF's margin over vector shrinks as the cause becomes more similar to the crisis (rho) and turns negative once the graph is noisy. | Margin stays above 0.05 for every rho with a noisy graph. |
| H5 | In the end task (LLM reader, fixed context budget, decoy causes that are present in memory), the graph's chain text alone, with zero retrieved memories, matches TCMF's decision accuracy. | TCMF memories beat chain-text-only by more than 0.05, CI excluding 0. |
| H6 | The temporal part contributes nothing: removing recency from TCMF's episodic term does not lower root_hit@5 in any condition. | Removing recency lowers root_hit@5 by more than 0.02 somewhere. |

Exploratory (reported, not in the corrected family): a graph-free multi-hop retriever versus
TCMF as memories increasingly mention their effects (beta); the two-stage rule "boosted memories
first, then episodic order" reproducing TCMF's top 5; question-agnostic boost on a status
question; chain depth beyond `max_depth=4`; wall-clock cost.

## Controls that must hold or the benchmark is broken

- `random` sits at `5/N` on every metric.
- `oracle` (gold first) sits at 1.00.
- TCMF on a **shuffled graph** (the true chain shape wired to unrelated events) must fall to the
  episodic baseline or below. If it stays high, relevance is leaking through something other
  than the graph.
- In the paper's own condition (cause orthogonal to crisis, chain-only perfect graph) TCMF must
  reproduce the paper's result, about 1.00, and vector about the floor. If it does not, my
  harness is wrong, not TCMF.
- Parity: my parametrized re-implementation used for ablations must return the identical
  ranking to the deployed `TCMFRetriever` on every scenario at default settings.
- End task: a no-memory reader sits at 0.25 (four options, position shuffled per scenario).

## Design

**Tier A, retrieval, synthetic vectors, offline.** Own generator (`tcmfaudit/world.py`), not
`tcmfbench`'s. The latent causal chain defines gold; the *observed* graph is a separate object
built by one of: `chain_only` (the paper's condition), `oracle` (all institution events as
nodes, true edges), `noisy(p_drop, n_false)`, `deployed` (the real `auto_link_predecessors`),
`shuffled`, `none`. Independent variables, one swept at a time from a fixed default:
cause-crisis similarity rho, effect-mention overlap beta, chain depth, graph mode and noise,
root age. n = 500 scenarios per cell, seeds 0-499, same seeds in every cell.

**Tier B, end task, real text and real embeddings, local models.** Templated incident worlds in
8 domains; four candidate causes per crisis, all four present in memory with witnesses, one
causally linked. Context budget fixed at 5 memories (or a summary of comparable length) for
every arm. Reader temperature 0, fixed seed. Arms: no memory, chronological, rolling LLM
summary, vector, episodic, two-hop vector, chain text only, TCMF on oracle / deployed / wrong
graph, gold. n = 120. Replication before any headline: second reader model and second encoder.

**TCMF itself is never re-implemented for a headline number**: the `tcmf_deployed` arm calls
`api.memory.tcmf.TCMFRetriever.retrieve` unmodified with its defaults. Baselines are written
from scratch in `tcmfaudit/retrievers.py` and share no code with `tcmfbench`.

## Confounds

| Confound | Handling |
|---|---|
| Baselines under-tuned relative to TCMF | Controlled: baselines have no tuned parameters; TCMF uses its shipped defaults, which the paper derived. Bias runs in TCMF's favour. |
| TCMF receives the crisis event id; baselines might not | Controlled: every graph baseline gets the same id. `none` mode measures its absence. |
| Synthetic geometry chosen by the auditor | Measured: every geometric assumption is a swept variable, including the paper's own setting as one cell. Accepted and stated for Tier B text, which is written by the auditor. |
| Pool size (the paper found claims die between 19 and 80 candidates) | Measured: default pool 35, repeated at 150. |
| Reader picks whichever option the context mentions | Controlled by design (all options present in memory) and measured (wrong-graph arm). |
| Answer-position bias of a 3B reader | Controlled: option order shuffled per scenario by seed. |
| One reader, one encoder | Replication arm; a result that does not replicate is reported as such. |
| The auditor wants TCMF to fail | Independent reviewer agents attack the design and the write-up; their objections are answered with runs, and listed. |

## What would change my mind

If H1, H2 and H5 all fail (TCMF beats the fusion-free graph reader, survives its own deployed
graph, and its retrieved memories beat the bare chain text), the architecture is doing real
work and the report will say so in its first line.

## Deviations

All made on 2026-11-13 after the first Tier A run, each because the first results exposed a
weakness in my own design. The pre-registered cells were not rerun or altered.

1. **`event_log` and `event_log_union` baselines added (experiments `P1_`, `P3_`).** The
   shuffled-graph control did not fall to the floor for the deployed retriever (0.55). To find
   out what was carrying it, I added a baseline that reads the event log but no edges. This is
   a post-hoc diagnostic and is labelled as one wherever it is reported.
2. **Few-symptom cells added (`P2_`).** H4 as registered cannot fail for TCMF: with six symptom
   memories and k = 5, vector retrieval scores exactly 0 on root_hit@5 at every rho, so the
   margin over vector says nothing about rho. `P2_` repeats the rho sweep with two symptoms so
   that vector has room to find a cause. The registered H4 outcome is reported as registered.
3. **Event-log size sweep added (`P3_`).** To test whether the deployed result depends on how
   many unrelated events the institution has logged.
4. **Summary prompt changed once, before the full Tier B run.** On a two-scenario smoke run the
   3B model copied the records as a list and was cut off mid-list. The prompt now asks for one
   paragraph and the output is truncated to 100 words. No accuracy number had been looked at.
5. **`graph_ppr` is reported but not used as a comparator.** It scores 0.000 almost everywhere
   because symptom memories attach to the crisis node and absorb the walk. That is an untuned
   baseline of mine failing, not evidence about PageRank retrieval; the existing paper's tuned
   PPR reaches 0.67 on its own benchmark.
6. **Results are stored gzipped** (`*.jsonl.gz`) to keep 80 MB of rows out of the repository.
7. **Tier B has n = 128, not 120** (8 domains x 4 true causes x 4 replicates), and is analysed
   over the 8 domains, not over scenarios.
8. **Changes made in answer to independent review** (full list in REVIEW_LOG.md): root_hit is
   reported at 5, 8 and 12 with MRR because production shows 8 of 12; H5's confirmatory arm is
   the production retriever, as registered, not the re-implementation I had first wired in; the
   wrong-graph arm no longer keeps the true mechanism; experiments `R1_` to `R3_` added
   (age-matched recency test, deep false edges, logs of 30 and 50 events); arms
   `event_log_union`, `tcmf_production_block_5@oracle` and
   `tcmf_production_block@deployed_graph` added to Tier B.
9. **The llama3.2 reader gets 12 output tokens, not 4.** At 4 tokens it wrote "The correct
   answer is" and was cut before the letter on 2,769 of 4,864 prompts, which the parser scored
   as wrong. That was my harness truncating the reader. The rerun at 12 tokens is the one
   reported; the truncated outputs remain in the cache file. The qwen reader answers with a
   bare letter and was not rerun.
