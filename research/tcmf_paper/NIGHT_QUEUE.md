# TCMF paper - 14-night hardening queue (2026-07-23 -> 2026-08-05)

**Purpose:** make the experiments impossible to argue with. Not wording polish. Every night
lands one self-contained, verifiable step: more scale, more domains, more baselines, stronger
ablations, real uncertainty quantification, and figures.

**Governing objection this queue exists to kill:**
> "Everything depends on a small handcrafted synthetic benchmark. Why should I believe this
> generalizes?"

Every item below is scored against that sentence. If a night's work does not move that answer
forward, it is the wrong night's work.

---

## How the night agent uses this file

1. Read this file. Take the **lowest-numbered item whose `Status:` is `OPEN` and whose
   `Env:` you can actually satisfy.** Do exactly one item. Do not batch two.
2. `Env: CLOUD-OK` = pure Python + numpy (+ pip-installable deps). Runs anywhere.
   `Env: LOCAL-ONLY` = needs Ollama on Zaid's machine (`nomic-embed-text`,
   `qwen2.5:3b-instruct`). A cloud agent must **skip** these, say so in the night log, and
   take the next CLOUD-OK item instead. Never fake an Ollama result.
3. Work in `research/tcmf_paper/`. Branch `night-tcmf/YYYY-MM-DD`. Open one PR on
   `syzayd/CivilizationOS`.
4. When the numbers land, **set `Status: DONE (YYYY-MM-DD)`** on the item and append the
   result to `NIGHT_LOG.md` (same folder), newest last.
5. **Report the result honestly, including when it damages the paper.** A night that
   discovers "the effect vanishes at a realistic pool size" is the most valuable night in
   this queue, not a failure. Write it down, do not retune until it looks good.

## Standing rules for every night

- **No number in the paper that was not produced by a committed script.** Every table and
  figure must be regenerable by a command written in `REPRODUCE.md`.
- **Deterministic and offline.** Seeded RNG, cached embeddings/LLM answers. No network in
  the eval path.
- **Pure-numpy statistics.** No scipy (not installed, and keeping the benchmark
  dependency-free is deliberate - `_personalized_pagerank` is already hand-rolled). Anything
  statistical gets a unit test against a hand-computed known answer.
- **Never tune on the test split** once N03 lands the split. Report test numbers only.
- No em dash (U+2014) anywhere. No Claude/Anthropic attribution in any commit or PR.
- The paper prose lives in the **private** repo `syzayd/tcmf-paper`. If the night agent
  cannot reach it, do the code and results work anyway and record the needed LaTeX delta in
  the night log as plain prose. Do not paste draft sections into the public repo.

---

## Phase 1 - Kill the scale objection (N01-N03)

### N01 - Larger candidate pool + multi-seed harness
**Status:** DONE (2026-07-24) | **Env:** CLOUD-OK | **Answers:** W4, W8 | **Risk:** HIGHEST - do first

The whole result set currently sits on a ~17-candidate pool where random scores recall@10 =
0.58. This is the load-bearing weakness, and it is the one that could invalidate later
nights' work, so it goes first.

- Add `--n-distractors`, `--n-noise`, `--seeds` (comma list) to `run_eval.py` and
  `run_mixed.py`; thread them into `GenConfig` (fields already exist) and `mixed.py`.
- Check `methods.materialize(max_mem_per_citizen=8)`: confirm the per-citizen prune does not
  silently re-cap the enlarged pool. If it does, that is a real finding - fix and note it.
- Rerun pure + mixed at **pool ~= 80** (20 distractors, 55 noise) across **5 seeds**.
- Recompute the random baseline analytically as a sanity check on the harness.

**Verify:** random's recall@10 falls to roughly k/pool (~0.12), not 0.58. Report whether
`tcmf_add`'s margin over every baseline survives at the realistic pool size, unchanged, and
at which k it survives. If the margin collapses, stop and write that up - it reframes the
paper and every later night.

### N02 - Bootstrap confidence intervals + paired significance tests
**Status:** DONE (2026-07-28) | **Env:** CLOUD-OK | **Answers:** W8

Averages alone will draw a reviewer complaint. Replace them everywhere.

- New `tcmfbench/stats.py`, pure numpy:
  - `bootstrap_ci(values, statistic, n_boot=10000, alpha=0.05, seed)` - percentile CI over
    scenarios, seeded.
  - `wilcoxon_signed_rank(a, b)` - exact for small n, normal approximation with continuity
    correction and tie handling for large n.
  - `holm_bonferroni(pvalues)` - the key contrasts are a family; correct for it rather than
    reporting a dozen naked p-values.
- Unit tests against hand-computed known answers (include a tied-ranks case and a
  zero-difference case; those are where signed-rank implementations break).
- Regenerate every `RESULTS*.md` table cell as `mean [lo, hi]`, and add a paired-test column
  for `tcmf_add` vs each baseline on per-scenario recall@5 and root_rank.

**Verify:** unit tests green; a contrast that is obviously null (e.g. a method against
itself) returns p ~= 1.0 and a CI containing zero.

### N03 - Held-out tuning split
**Status:** DONE (2026-07-30) | **Env:** CLOUD-OK | **Answers:** W5

Right now lambda = 4 and tau are picked with the eval set in view. That is a straight
"tuned on test" objection and it is cheap to remove.

- Partition scenario seeds into `tune` (40%) / `test` (60%) by seed, disjoint and fixed.
- Sweep on `tune` only: `tcmf_add` lambda, `tcmf_mult` lambda, RRF `c`, `causal_only` tau,
  `graph_ppr` alpha. **Every operator gets an equal sweep budget** - state the budget.
- Report all headline numbers on `test` with the tune-selected values.

**Verify:** a table of selected hyperparameters and their tune-set scores, separate from the
test-set results table. Confirm the headline ordering is unchanged from N01; if the ordering
moves, that is the honest result.

---

## Phase 2 - Kill the "one setting" objection (N04-N06)

### N04 - Spurious-edge robustness
**Status:** DONE (2026-07-31) | **Env:** CLOUD-OK | **Answers:** W7

Only *missing* edges are stressed today (dropout). Wrong edges are the more dangerous
failure: a false ancestor injects a confident wrong boost. Reviewers will ask for exactly
this.

- Inject false ancestor edges at rate p in {0, 0.05, 0.1, 0.2, 0.4}, independently of the
  existing dropout knob; then run the 2-D grid (dropout x spurious) at a coarse resolution.
- Report precision-side damage, not just recall: how often a *distractor* is promoted into
  the top-5 by a spurious edge.

**Verify:** at p = 0 the numbers reproduce N01 exactly (same seeds). Degradation is
monotone in p. Report the p at which `tcmf_add` drops below `semantic_rag` - that number is
the paper's honest operating-envelope claim.

### N05 - Second-domain corpus (authoring only, no embedding)
**Status:** DONE (2026-08-04) | **Env:** CLOUD-OK | **Answers:** the generalization objection (part 1)

The benchmark is one causal setting (governance/civilization crises). One more domain makes
the contribution much harder to dismiss.

- Extend `realtext.py` with two new domains, same `Scenario` contract, `domain` field set:
  - **software-debugging** - incident postmortem: a config/dependency change days earlier is
    the root cause; the symptoms are loud downstream alerts.
  - **cybersecurity** - intrusion kill chain: initial access is the root cause; the symptoms
    are late-stage exfiltration alarms.
- Both must preserve the regime the paper is about: the root cause is **semantically
  dissimilar** to the crisis, the distractors are semantically **similar** to it. Author the
  decoys for the decision tier at the same time (3 plausible external-shock decoys each,
  matching `decision.py`'s existing structure).
- Ship text + unit tests only (structure, field presence, no-embedding assertions). Do not
  attempt to embed.

**Verify:** tests green; a written justification per domain that the dissimilarity regime
holds by construction. Hand the embedding/run to N06.

### N06 - Second-domain run + decision tier
**Status:** DONE (2026-08-06) | **Env:** LOCAL-ONLY (needs Ollama) | **Answers:** the generalization objection (part 2)

- Embed the N05 corpora (`nomic-embed-text`), retune tau **on the tune split only** per
  domain, run the full 8-method set plus the decision tier on both new domains.
- Commit the extended `emb_cache.json` / `llm_cache.json` so cloud nights can rerun offline.

**Verify:** the qualitative story (additive >> multiplicative; decision accuracy tracks
causal recall) either replicates in both new domains or does not. **Report per-domain,
never pooled** - pooling would hide a domain where it fails.

---

## Phase 3 - Kill the "wrong baselines" objection (N07-N08)

### N07 - Additional retrieval baselines
**Status:** DONE (2026-08-05) | **Env:** CLOUD-OK | **Answers:** W3, W6

Add baselines that are reimplementable *mechanisms*, and be precise that they are mechanism
analogues, not system reimplementations.

- **MMR** (maximal marginal relevance) - the standard diversity re-ranker; tests whether
  plain diversification already surfaces the causal ancestors.
- **BM25 lexical** - tests whether the effect is an artifact of dense embeddings.
- **Summary-buffer / paging retrieval** (MemGPT-style mechanism) - recent window plus a
  compressed older summary.
- **Community-summary retrieval** (GraphRAG-style mechanism) - cluster the event graph,
  retrieve via cluster summaries.
- **Extract-and-consolidate memory** (Mem0-style mechanism) - dedupe/merge memories before
  ranking.

Name each in code and prose as "X-style mechanism, not a reimplementation of X", the same
correction already applied to `graph_ppr` / HippoRAG.

**Verify:** every new baseline beats `random` on at least one metric (a baseline that cannot
is misimplemented, not weak). Run under the N03 protocol with equal tuning budget.

**Residual, investigated and explained, not a bug:** in the PURE regime specifically, 3 of the
5 new baselines (`bm25`, `community_summary`, `extract_consolidate`) beat `random` on NO
metric - traced to real, deterministic properties of the mechanism against this benchmark's
adversarial construction (see NIGHT_LOG.md 2026-08-05), not an implementation defect (all 5
comfortably beat random in the MIXED regime, and unit tests + hand-computed cases pass). The
single most important number either way: `causal@5` for all 5 new baselines is <=0.05 in BOTH
regimes (mostly exactly 0.00), against TCMF's 1.00 - none of them ever meaningfully recovers a
causal ancestor.

### N08 - Related-work differentiation table + citation verification
**Status:** DONE (2026-08-01) | **Env:** CLOUD-OK | **Answers:** W3, and the standing "verify every arXiv ID" gate

**Residual before submission:** three added entries (Zep, A-MEM, Mem0) have verified IDs,
titles and years but incomplete author lists, flagged in `references.bib` notes. Read them off
the PDFs. Everything else resolved.

- Use web search to **verify every entry in `references.bib` against its canonical source**.
  Never ship an arXiv ID from memory. Fix or remove anything that does not resolve.
- Add verified entries for the systems reviewers will name: Mem0, LightMem, MemGPT, GraphRAG,
  HippoRAG, LongMem, Zep/Graphiti, A-MEM.
- **Added 2026-08-01 from an external reviewer pass:** also search for and verify, or
  explicitly record as non-existent, the 2026-vintage systems named in that review: REMem,
  MAGMA, HINDSIGHT, and the "event-causal RAG" line. These were reported second-hand, so
  treat every one as unverified until resolved against a canonical source. An LLM-suggested
  citation that does not resolve is a hallucinated reference, and shipping one is worse than
  omitting it. Record the outcome per name either way.
- Produce a differentiation table with one row per system and columns:
  *structure used | retrieval operation | task solved | why it does not address the
  causal-ancestor regime*. The claim to defend is not "nobody did memory" - it is "none of
  these rank by causal-ancestor reachability from the current crisis, and none report the
  fusion-operator effect."

**Verify:** every citation resolved against a real source with the ID recorded in the bib
comment. Any system that turns out to actually do causal-ancestor retrieval gets flagged
loudly to Zaid - that would be a novelty problem, and it is better found now.

---

## Phase 4 - Figures (N09-N11)

Figures buy more reviewer confidence than another page of prose. All figures: vector PDF via
matplotlib, single-column readable (3.3in wide, >= 8pt effective font), colorblind-safe,
regenerated by `figures/make_figures.py` from committed result JSON - **never hand-drawn and
never hand-typed numbers**. Add `research/tcmf_paper/requirements-bench.txt` (matplotlib) in
N09; matplotlib is not currently installed locally.

### N09 - Fig 1 (causal graph) + Fig 2 (retrieval pipeline)
**Status:** DONE (2026-08-06) | **Env:** CLOUD-OK

- **Fig 1:** a real scenario's causal graph - crisis node, its ancestor chain, the root
  cause, the semantically-similar distractors sitting *off* the causal path. This single
  figure is what makes the paper's premise legible in ten seconds. Draw it from actual
  scenario data, not a cartoon.
- **Fig 2:** the retrieval pipeline - memories -> episodic score, crisis -> bounded backward
  BFS -> ancestor set -> boost, then the fusion box -> ranking.

**Verify:** render each to PNG and actually look at it. Check overlap, legibility at column
width, and that Fig 1's node labels match the scenario JSON it was generated from.

### N10 - Fig 3 (fusion operator) + Fig 4 (recall vs lambda)
**Status:** DONE (2026-08-06) | **Env:** CLOUD-OK

- **Fig 3:** the paper's core claim as a picture. **The brief here was rewritten 2026-08-04 -
  the original said to show "why multiplication annihilates a causal signal riding on a
  near-zero episodic score", and N15 measured that to be FALSE.** The root cause's episodic
  score is not near zero (0.96 against a distractor's 2.48), and impossibility occurs in only
  about 1 of 200 root-cause/distractor pairs. Draw the actual mechanism instead: both
  operators' pairwise margins are affine in lambda (`theory.py`), so plot margin vs lambda for
  several real root-cause/distractor pairs, two panels. Multiplicative: the zero-crossings
  scatter across lambda because each depends on that pair's episodic scores, so no single
  vertical line separates all of them. Additive: every crossing sits left of the
  `1/(b_root - b_distractor)` bound, which is drawn as one vertical line independent of
  episodic score. The picture to leave in the reader's head is "one line works for additive,
  no line works for multiplicative", not "multiplying by zero gives zero."
- **Fig 4:** recall vs lambda for both operators on one axis, with N02 confidence bands. The
  flat low-lambda region of the multiplicative curve is the evidence for "a practitioner
  tuning lambda would never stumble onto the fix" - make that region visually obvious. Mark
  the tuned lambda=2.4 point too (recall@5 0.54), so the figure does not imply the
  multiplicative operator is flat everywhere.

**Verify:** generate Fig 3 from `theory.py`'s `mult_crossover_lambda` /
`additive_sufficient_lambda` on real scenario pairs, not from hand-drawn geometry, and check
that every plotted additive crossing really does fall below its drawn bound.

**Independent second build, then reconciled (2026-08-11):** a second session built Fig 3/Fig 4
independently before discovering N10 was already DONE (a Night Shift collision - see
[[night-shift-collision-lesson]] in memory). Both builds converged on the same Fig 3 design (one
root-vs-hardest-distractor pair per seed, same 10 seeds `run_theory.py` sweeps); the second
build's version is the one kept (`test_n10_n11_figures.py` cross-checks every pair against
`results_theory.json`'s own `mult_required_lambda` and asserts every additive crossing sits at
or below its bound). Fig 4 keeps the original `run_lambda_sweep.py`-based build (its tuned
lambda=2.4 point, recall@5=0.52, comes from the actual N03 held-out tune/test split - the
second build's own attempt at this point, 0.55, ran the full dataset directly through the same
lambda value without going through the held-out split, which is a materially weaker claim for a
point explicitly labeled "held-out tuned"; superseded and not carried forward, though its
`mult_lambda` ablation in `run_eval.py` remains as a harmless, independently-useful addition to
`results_main/results.json`).

### N11 - Fig 5 (graph degradation) + Fig 6 (decision accuracy)
**Status:** DONE (2026-08-07) | **Env:** CLOUD-OK

- **Fig 5:** degradation under edge dropout *and* the N04 spurious-edge rate, with CI bands
  and the semantic floor drawn as a reference line.
- **Fig 6:** decision accuracy per method with CIs, plus the `no_retrieval` floor and
  `oracle` ceiling as horizontal reference lines. This is the paper's punchline figure -
  retrieval choice changes the decision.

**Residual, found and recorded, not fixed (out of scope for a figures-only item):**
`results_decision/results_decision.json` never stored a per-scenario array, only
`(mean, std, n)`, so Fig 6's CIs come from a closed-form Wilson score interval on `k` recovered
exactly from the committed mean (`tcmfbench.stats.wilson_ci`, new), not from bootstrapping a
real per-scenario array. Attempting to rerun `run_decision.py` to get that array instead failed
outright on a clean CLOUD-OK checkout: `realtext.DOMAINS` grew from 6 to 8 entries after N05,
so the same seed now draws a different, uncached scenario sequence. See REPRODUCE.md and
NIGHT_LOG.md 2026-08-07 for the full trace and the fix recommendation for whoever next touches
`run_decision.py`.

**Verify:** every plotted value matches the source JSON exactly (assert it in the script, do
not eyeball it).

**Independent second build, then reconciled (2026-08-11):** the same Night Shift collision that
hit N10 hit N11 too. Fig 6 keeps the original build (Wilson score interval via
`tcmfbench.stats.wilson_ci` - the statistically correct choice given `results_decision.json`
only ever stored `(mean, std, n)`, not a per-scenario array to bootstrap; the second build's own
Fig 6 used a normal-approximation CI from the same mean/std, which under-covers near the
boundary where `tcmf_shipped` sits at 0.97 - superseded and not carried forward).

Fig 5 keeps the SECOND build's two-panel design instead of the original's single-axis one, for a
reason worth flagging rather than burying: the original build's dropout panel read
`results_mixed_scale`'s own `dropout_curve` (realistic pool) directly, which - unnoticed by that
build - already shows `tcmf_add` falling BELOW the `semantic_rag` floor at dropout >= 0.5 (0.41
at 0.5, 0.32 at 0.75, 0.25 at 1.0 vs the floor's flat 0.40), the opposite of F7's "converges to
the semantic floor, never below" claim, which was only ever verified at the small pool. **This
is a real, measured, unreconciled result, not a bug in either build** - a CI'd rerun of the same
curve (`run_spurious.py`'s new `dropout_curve`, same protocol as its existing spurious-rate
curve) reproduces it bit-for-bit. The kept Fig 5 anchors its dropout panel to `results_mixed`'s
small-pool `dropout_curve` (Table `tab:dropout`'s own published numbers) instead, and its
spurious-edge panel to `results_spurious`'s existing CI'd `curve`.

**Reconciled 2026-08-11 (F9b), the same way Section 5.3 (F9) already reconciled recall@10's
pool-size sensitivity:** `main.tex` now states the realistic-pool numbers explicitly (new
`sec:pool-scale` finding F9b: `tcmf_add` recall@10 $0.80\to0.57\to0.41\to0.31\to0.25$ against a
flat $0.40$ floor as dropout goes $0\%\to100\%$, crossing below the floor between 50% and 75%
dropout, CI-confirmed at 75%) and explains the mechanism (at 100% dropout `tcmf_add`'s score
reduces to the normalized *episodic* score alone, not the *semantic* score `semantic_rag` uses,
so the two have no reason to coincide at any pool size). F7's own claim, the abstract/intro
bullet, the Limitations "Missing vs. spurious edges" paragraph, the Conclusion, and Fig 5's
caption were all updated to scope the floor-convergence claim to the small pool - the
relative-ordering claim (`tcmf_add` $\ge$ `causal_only` throughout) was never pool-size sensitive
and needed no change. Builds clean at 25 pages, 0 undefined refs, same 4 pre-existing overfull
hboxes.

---

## Phase 5 - Ablations and closing (N12-N14)

### N12 - Leave-one-out ablation of the four shipped fixes
**Status:** DONE (2026-08-11) | **Env:** CLOUD-OK

The paper claims four defects mattered. Prove each one's individual contribution instead of
asserting it.

- Ablate independently: (1) additive vs multiplicative fusion, (2) crisis-excluded-from-
  own-ancestors, (3) favor-root depth weighting, (4) per-citizen top-8 prune removed.
- Report full method, minus-one for each, and the interaction between (1) and (3) - N06/F8
  suggests those two interact, since favor-root is what lifts `tcmf_shipped` above
  `tcmf_add` on decisions.
- Also sweep: tau sensitivity, BFS depth cap, and top-k.

**Verify:** the four effects sum roughly to the full gap, or they do not and the interaction
is quantified. Run under N03's protocol with N02's CIs.

**Scope actually covered (2026-08-11):** `methods.rank_tcmf_ablation` (new) toggles all four
fixes independently on the same episodic scores/causal boosts every other variant shares;
cross-checked bit-for-bit against `rank_tcmf_additive`/`rank_tcmf_multiplicative` at the
all-fixed/all-broken extremes (`test_n12_ablation.py`, 6 tests). `run_ablation.py` reports the
7-arm leave-one-out table, the fix1xfix3 interaction (on both recall@5 and root_mrr, since fix3
alone moves only the latter - matches F5's own "decides which ancestor, not whether" framing),
and the tau/BFS-depth-cap sweeps, at the pure regime's `results_main`-identical pool.
**Two real, non-obvious findings, not hedged:** (a) fixes 2 and 4 measure as null in isolation
at this pool - fix 2 because the true ancestors out-boost the leak regardless, fix 4 because the
benchmark's own `materialize()` never lets a citizen exceed the old prune cap by construction, a
structural fact rather than a substantive one. A supplementary run with citizens forced to hold
more memories than the old cap (realistic pool, `max_mem_per_citizen=32`) makes fix 4's effect
dramatic: recall@5 $1.00\to0.14$. Also checked fix 2 in the mixed regime (its natural habitat,
distractors near the crisis's own topic) - still null. (b) the fix1xfix3 interaction is real:
reverting both costs far more recall@5 than the two isolated drops summed (residual $+0.18$;
$+0.08$ on root_mrr). Written into `main.tex` as a new Section 6.1. Builds clean: 26 pages, 0
undefined refs, same 4 pre-existing overfull hboxes (one new one introduced by this section's
own math, fixed before commit).

### N13 - Second encoder + latency
**Status:** OPEN | **Env:** CLOUD-OK for the encoder (sentence-transformers, pip), LOCAL-ONLY if using a second Ollama model

- Re-run the real-text tier under a second encoder (e.g. a sentence-transformers MiniLM) to
  show the effect is not an artifact of `nomic-embed-text`, and to show the anisotropy
  threshold is **encoder-specific** (0.45 -> 0.60 was a nomic fact, not a universal one).
  Report the per-encoder tuned tau side by side.
- Measure retrieval latency: bounded backward BFS + fusion vs plain semantic ranking, as a
  function of graph size. Cheap, and it pre-empts "what does this cost?"

**Verify:** the ordering of methods is preserved across encoders. If it is not, that is a
major finding and the paper's claim must narrow to "for this encoder family."

### N14 - Full regeneration, reproducibility pack, paper integration
**Status:** DONE (2026-08-06) | **Env:** LOCAL-ONLY (needs Ollama for the real-text/decision tiers)

- One command regenerates every table and figure from scratch. Write `REPRODUCE.md` with
  exact commands, expected runtimes, and which artifacts are cache-backed.
- Confirm every number in the paper traces to a committed artifact. Any orphan number is a
  bug - find its source or delete the claim.
- Rewrite `paper/REVIEW.md`'s venue verdict against the *new* evidence base, and re-run the
  LaTeX structural validation (brace balance, no U+2014, all citations resolve, table column
  counts).

**Verify:** a clean clone plus the caches reproduces every headline number bit-for-bit.

**Scope actually covered (2026-08-06):** `REPRODUCE.md` documents every result directory that
exists as of this date, with the exact command that regenerates it, verified by rerunning several
fresh (not just trusted from old logs - this caught `results_main_pool80`/`results_mixed_pool80`
as stale/superseded by `results_*_scale`, already explained in FINDINGS.md's N01 addendum, not a
new bug). `paper/REVIEW.md`'s build-status note and venue verdict were updated against the current
evidence base, including N06. N07/N09-N13/N16/N17 have no artifact yet - `REPRODUCE.md` says so
explicitly rather than guessing at their eventual runtime; each gets a row the day it lands, and
whoever completes one of those items should re-check this item's REVIEW.md verdict too.

---

## Phase 6 - Added 2026-08-01 after an external reviewer pass (N15-N17)

An outside review (scorecard: novelty 8, technical quality 9, experimental design 9,
reproducibility 9, overall 8.5) raised four things this queue did not already cover. One was
prose framing, which stays out of scope; the other three are below. The review's remaining
recommendations mapped onto existing items: figures to N09-N11, recent-baseline comparison and
citation verification to N07-N08, robustness breadth to N01/N04.

### N15 - Formal proposition for the fusion-operator effect
**Status:** DONE (2026-08-01) | **Env:** CLOUD-OK | **Answers:** W2, and the "is this a new
algorithm or an empirical study?" positioning question

The single gap the 14-night queue had no item for: every night here is empirical, so a
reviewer asking "why should this generalise beyond your benchmark?" had only more tables as an
answer. Shipped: `tcmfbench/theory.py`, `tcmfbench/test_theory.py` (17 tests),
`tcmfbench/run_theory.py`, `results_theory/`, and `THEORY.md`.

Result: both operators' pairwise margins are affine in lambda, so multiplicative fusion's
required lambda depends on the episodic scores and admits no bound in terms of the causal
margin (Prop 1), while additive fusion's is bounded by `1/(b(r) - b(d))` independently of the
episodic scores (Prop 2), and a lambda sweep on the multiplicative form interpolates toward the
`e*b` ordering rather than the causal one (Prop 3). Measured: multiplicative's requirement
swings 3.0x across seeds, additive's 1.10x, and the shipped `lam = 4` is exactly the Prop 2
bound. **Honest scope limit recorded in `THEORY.md`:** outright impossibility is rare (1 of 200
pairs) and is a boost-function defect, not a fusion defect, so the claim is "additive admits one
scenario-independent lambda, multiplicative does not" and NOT "multiplicative can never work."

### N16 - Scale and multi-crisis stress
**Status:** DONE (2026-08-11) | **Env:** CLOUD-OK | **Answers:** the generalization objection (part 3)

The external review asked for larger memory sizes and multiple simultaneous crises; N01 took
the pool to 80, which is still small next to a real deployed agent's memory.

- Scale the pool to 1000+ memories per scenario and report where, if anywhere, the margin
  degrades. Watch runtime: the bounded backward BFS should stay cheap, plain ranking is O(pool),
  so record the measured cost as a function of pool size (this also feeds N13's latency item).
- Add a **multi-crisis** scenario mode: two or more concurrent crises with interleaved causal
  chains and a shared distractor pool, where a memory can be an ancestor of one crisis and
  irrelevant to another. Report whether the causal boost still discriminates when the ancestor
  set is no longer unambiguous.

**Verify:** at pool 80 the numbers reproduce N01 exactly (same seeds). Report the pool size at
which `tcmf_add`'s causal@5 margin over `graph_ppr` closes, if it closes. Per-crisis metrics in
the multi-crisis mode, never pooled.

**Scope actually covered (2026-08-11):** `run_scale.py` sweeps 5 pool points (17, 78, 378,
978, 1503, `chain_len` fixed - graph size never scales, only the memory pool does), `n=30`/point
for recall (bootstrap CI) and `n=15`/point for latency (median of one timed call each). Pool 17
and 78 reproduce the existing small/realistic-pool config exactly (`test_n16_scale.py`
confirms this at the config level). **Finding (F12): the causal@5 margin never closes** -
`tcmf_add` holds 1.00 through pool 978 and is still 0.99 at 1503, against `graph_ppr`'s flat
0.333 (its PPR mass depends on the fixed graph, not the pool). Latency confirms the structural
claim: BFS-only stays ~flat (0.004ms to 0.010ms across an 88x pool increase) while plain
semantic and full fusion both grow roughly linearly with the pool (~113-119x); fusion costs a
constant ~3-4x over semantic at every scale, not a growing multiple.

`multi_crisis.py` (new module) builds one combined scenario per point - every crisis's chain in
one shared graph, one shared memory pool, materialized once - then scores each crisis
separately via `crisis_scoped_mat` (swaps only the query/gold fields, shares everything else).
`run_multi_crisis.py` sweeps 2/3/4/8 concurrent crises, `n=60` scenarios/point.
**Finding (F13): the causal boost discriminates cleanly** - even at 8 simultaneous crises,
causal@5 stays at 0.999 and cross-crisis boost leakage stays ~3 orders of magnitude below the
true own-crisis boost (0.0023 worst case vs. 0.571 mean), because bounded backward BFS from one
crisis's event structurally cannot reach another chain that shares no edges with it -
`test_n16_scale.py` asserts this leakage is exactly 0.0 in the 2-crisis case.

Both written into `main.tex` as new Section 5.8 (`sec:scale-stress`), and the existing
"Candidate pool" limitation was narrowed to state explicitly that it now applies only to the
aggregate recall@10 metric, not the causal-ancestor subset. Builds clean: 27 pages, 0 undefined
refs, same 4 pre-existing overfull hboxes (two new ones from this section's own table/paragraph
widths, both fixed before commit).

### N17 - TCMFBench as a standalone contribution
**Status:** OPEN | **Env:** CLOUD-OK | **Answers:** long-term impact

The external review's strongest strategic point: a benchmark that other researchers actually
run outlives the paper that introduced it, and TCMFBench already tests a failure mode
(semantic similarity disagreeing with causal relevance) that mainstream RAG benchmarks do not.

- Give it a small stable public API: register a retriever as a callable
  `(materialized_scenario) -> ranked_ids`, run it across every tier, get the standard metric
  table back. Everything else here is currently reachable only by editing the run scripts.
- Write the README section a stranger needs: what regime it tests, what the tiers are, how to
  add a method, what the baselines are, expected runtimes.
- Only after N14 freezes the evidence base. Do NOT publish anything outward-facing before Zaid
  says so; this item is preparation, not release.

**Verify:** a retriever written against the public API alone, with no edits to `tcmfbench`
internals, reproduces a known baseline's published numbers exactly.

### N18 - Does the regime occur in public data?
**Status:** DONE (2026-08-01) | **Env:** LOCAL-ONLY (needs Ollama) | **Answers:** the
generalization objection at its root

The sharpest objection available to a reviewer is not "does additive beat multiplicative on
TCMFBench" - that is now thoroughly established - but **"is the regime real, or did you build
a simulator that exhibits it?"** Every other item in this queue is measured on scenarios we
authored, so none of them can answer that. This one can.

Measured on **LoCoMo** \citep{maharana2024locomo}, a public human-verified long-term
conversation benchmark: take its multi-hop questions, rank every unit of the conversation by
similarity to the question, and see where the annotated gold evidence lands. Shipped
`tcmfbench/locomo_regime.py`, `run_locomo_regime.py`, `test_locomo_regime.py` (10 tests,
CLOUD-OK because they use hand-built vectors), `results_locomo/`.

**Two hard constraints this item established, both worth respecting later:**

- **Neither LoCoMo nor LongMemEval ships a causal graph.** LoCoMo builds temporal event graphs
  with causal links during *generation*, but the release does not expose them: `event_summary`
  is free text per speaker per session with no ids and no edges. LongMemEval is chat history
  plus `answer_session_ids` pointers. So TCMF itself **cannot be run** on either without
  inducing a graph, which is out of scope and upstream of TCMF (and whose errors would
  dominate, per W7). This is a motivating measurement, NOT a TCMF evaluation. Do not let it
  drift into being described as one.
- **Granularity is a confound and it bit once.** The first version of this measurement ranked
  single dialogue turns and reported recall@5 = 0.066. That number is mostly an artifact of
  the retrieval unit; at session granularity, which is what real systems use, it is ~0.50.
  **Report the session rows.** The turn rows stay in the results file as the honest record of
  why the headline is what it is.

**Verify:** `results_locomo/results_locomo.json` regenerates from the committed script given
the dataset plus Ollama; the 10 unit tests pass without Ollama; the reported figures are the
session-granularity ones.

---

## Deliberately out of scope for these 14 nights

- Wording and prose polish. Lower return than any item above; do it after the evidence base
  is frozen at N14.
- A real Zep or A-MEM system reimplementation (N08 covers them by differentiation instead).
  Only worth it if aiming above workshop, and it is a multi-week job on its own.
- Anything outward-facing: no arXiv posting, no publishing the draft, no external PRs. The
  paper stays private until Zaid says otherwise.
