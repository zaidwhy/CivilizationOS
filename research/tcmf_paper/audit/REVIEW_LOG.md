# Independent review log

An independent reviewer (a separate model session with no access to my conclusions, told to
find reasons the audit itself is wrong in either direction) read the pre-registration, the
code and the raw results on 2026-11-13, after Tier A's first run and before Tier B had data.
It returned 18 objections. Each is listed with what was done. Where the reviewer was right and
the audit's first reading was wrong, that is stated.

The reviewer is an AI model, not a qualified human researcher. It does not replace one.

| # | Objection | Verdict | What changed |
|---|---|---|---|
| 1 | The top-5 cutoff manufactures two effects. The default world has 6 symptom memories and 6 unrelated events, both just above 5; production shows the council 8 of 12. At k = 8 the "root never retrieved" results become "root at rank 7". | **Correct. My first reading overstated H1 and H3.** | Every table now reports root_hit at 5, 8 and 12 and root MRR. The report states the top-5 results as rank damage, and rests the weak-ancestor finding on the event-log size sweep, where it holds at 8 and 12. |
| 2 | Pre-registration not verifiable: deviations empty, folder uncommitted. | Partly correct. Deviations had been written but after the reviewer read the file; nothing was committed. | Deviations completed. The folder is committed in one commit, so the ordering of PREREG.md against results rests on my word, not on git history. Stated in the report's limitations. |
| 3 | H1 was tested only where the fusion-free reader is guaranteed 1.0. On chains of depth 4 to 6 TCMF's depth weight beats it by 0.24 to 0.51 at top 5. | **Correct, and it favours TCMF.** | Reported as a real contribution of the depth weight. H1 is recorded as supported for chains that fit in the cutoff and refuted beyond it. |
| 4 | Vector scores 0 by construction, so H2 and H4 are trivial wins for TCMF. | Correct. | Already disclosed (deviation 2); the report compares against the edge-free `event_log` baseline instead and does not cite TCMF's margin over vector in Tier A as evidence. |
| 5 | "Deployed" means the class, not the system: in the engine, crisis observations are stored without embeddings (`engine.py:448-449, 481-483`), importance is fixed per kind, and with `use_llm=False` no router is passed. | Correct. Verified by reading the engine. | Arms renamed in prose to "production retriever". The embedding gap is reported as a code-reading finding, not a measurement. No engine replay was run; listed under limitations. |
| 6 | A 10-event log never exercises the 20-event window, and the shuffled-graph control failed without being reported as failed. | Correct. | Log sizes 30 and 50 added (`R3_`). The failed control is reported as the finding it is. |
| 7 | The noise model only ever makes unrelated events shallow, which a root-favouring weight forgives. | Correct. | `R2_` adds false edges that make an unrelated event the deepest node. |
| 8 | H6 could only come out against recency because the root is built older than the unrelated events. | **Correct. My +0.13 was mostly a design artifact.** | `R1_` matches the two age distributions: the effect shrinks to +0.02 at top 5 and 0 at top 8. H6 is reported as "recency does not help" and no longer as "recency hurts". |
| 9 | Equivalence is claimed from point-null tests; many differences are identical on all seeds, so p-values measure determinism. | Correct. | Verdicts now compare the interval with the registered 0.05 margin and say when two arms are identical on every scenario. Holm is applied to the registered family only. |
| 10 | Tier B's chain-text arm names exactly one option, so H5 is ceiling against ceiling; and the primary arm was the re-implementation, against the pre-registration. | Correct on both. | H5's confirmatory arm is now the production retriever. The chain-text result is described as what it is: with a correct graph the answer is in the graph. |
| 11 | The 32 clusters share text within a domain; effective n is 8. | Correct. | All Tier B intervals and tests are over the 8 domains. |
| 12 | The wrong-graph arm kept the true mechanism event. | Correct. | The wrong graph now carries the impostor decision's own mechanism. |
| 13 | The production-block arm showed 8 memories against a budget of 5 and logged no shown memories. | Correct. | Logging fixed; a 5-memory variant added; an end-to-end arm on the production linker's graph added. |
| 14 | `graph_ppr` is a strawman. | Correct. | Never cited as a comparator (deviation 5). |
| 15 | `two_hop` cannot work at beta = 0. | Correct. | Reported as exploratory; its Tier B result is reported with its failure to replicate across encoders. |
| 16 | The similarity threshold is inert in the synthetic geometry. | Correct. | Stated. Tier B shows why it matters with a real encoder. |
| 17 | The `link_all` comment was backwards. | Correct. | Comment fixed. |
| 18 | Tier B had no data and no replication at review time. | Correct at that time. | Run since: two readers, two encoders. |

Things the first reviewer checked and found sound: the stored rows regenerate exactly from the
current code (6,015 rows, 0 mismatches); the ablation re-implementation matches the production
retriever on all 2,500 paired ablation scenarios; the adapter is a faithful call of
`TCMFRetriever.retrieve`; no baseline sees ground truth; `random` sits at 5/N and `oracle` at
1.0; answer positions are balanced.

## Second review: fact-check of the finished report

A second independent model session checked REPORT.md against the raw rows and the production
source: it recomputed Tier A from `*.jsonl.gz`, Tier B from the row files, regenerated worlds
for numbers no file stores, and read the engine. It confirmed nearly every number (all 48
values of the log-size table, every Tier B cell, the ablations, the code-reading claims) and
found these problems, all fixed in the report:

| Kind | Problem | Fix |
|---|---|---|
| number | Graph-reader cost given as 3.2 ms; the file says 3.6 to 4.7 ms | corrected |
| number | The 2.6 ms "paper configuration" timing was the shipped scoring, vectorized | relabelled |
| number | "Summary is the weakest once evidence exists" is false in every file | now "trails vector" |
| number | Root witness in shipped top 5: 1 of 256, not 1 of 128 | corrected |
| number | "27% of unrelated decisions linked" is nomic only; MiniLM is 6% | both given |
| wording | "Identical top 5 on 500 of 500": only per-scenario metrics are stored, and in Tier B the two readers show the same five memories in 24 to 75 of 256 scenarios | reworded; the Tier B count is reported |
| wording | "Only the depth weight changes any outcome" ignores lambda and symptom recall | scoped to root placement above lambda 2 on a clean graph |
| wording | "Chain text does better than either" is resolved in about half the cells | now "matches or exceeds" |
| wording | The depth-weight gain of 0.24 to 0.51 mixed two retrievers; beyond depth 4 the paper configuration scores 0 and loses | table and text separated by retriever |
| **framing** | **"Linked the true root in 0 of 500" is guaranteed by the 48-tick window, not measured** | **stated as by construction; the in-window cells carry the measurement** |
| wording | "No evidence the graph can be had" ignored the recent-and-similar cell, where the linker works | scoped to the paper's regime |
| wording | "A wrong graph" is one coherent wrong graph, and the range omitted the link condition | described and widened |
| wording | "Every arm shows 5 memories" is false for three arms | budgets listed |
| **overreach** | **The end-to-end gain over vector rested on the over-budget arm; budget-matched it is +0.06, +0.06, +0.13 and resolved in one pairing** | **both rows shown; marked exploratory** |
| wording | "Better with a bad graph than a good one" holds with nomic only | scoped |
| wording | tcmfbench is not all chain-only: N16 and N29 add other events but use the clean ancestor map | corrected; the point to the paper is stronger |
| omission | H4 is refuted as registered, and the repaired `P2_` cells were never reported | registered-outcomes table added |
| omission | Seven of my own errors from the first review were missing from "What I got wrong" | added |
| omission | With `use_llm=False` no memory has an embedding at all | added, as a code-reading finding |
| omission | Results favourable to TCMF were understated (no top-8 drop at 6 events; rescue of missing edges at top 5; improvement with false edges) | added to Finding 2 |
| omission | The paper configuration runs a nomic-tuned threshold under MiniLM | disclosed |
| omission | The paper-configuration numbers are not production calls, and parity covered only the default path | disclosed; parity test added for the rule-off path |
| omission | Replication is three pairings, not four | stated |

Not done, and still open: a second review of the finished report by a human who works on
retrieval or agent memory.
