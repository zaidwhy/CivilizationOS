# TCMF Night Log

Append-only, one entry per night, newest last. Written by the nightly hardening routine
(see `NIGHT_QUEUE.md`).

Each entry must record: which queue item, why it was chosen, **what the numbers actually
said** (including when they hurt the paper), what was verified vs assumed, and the LaTeX
delta the private paper repo needs.

---

## 2026-07-23 (setup, not a night task)

- **Task:** Built the 14-night hardening queue (`NIGHT_QUEUE.md`) and registered the nightly
  cloud routine that works it.
- **Why:** The paper's evidence base, not its prose, is what stands between it and a
  reviewer's "this is a small handcrafted synthetic benchmark." Two weeks of one-step-per-
  night on scale, domains, baselines, ablations, uncertainty, and figures.
- **Result:** Queue N01-N14 written, ordered so the riskiest item (N01, larger candidate
  pool) runs first - it is the one that could invalidate every later night. N06 and N14 are
  flagged LOCAL-ONLY (Ollama); the cloud agent skips them and takes the next CLOUD-OK item.
- **Verified:** benchmark inventory confirmed against the real tree - `GenConfig` already
  carries `n_distractors` / `n_noise` (so N01 is a threading job, not a rewrite), `run_eval`
  and `run_mixed` currently expose only `--n/--seed/--out`, no scipy and no matplotlib are
  installed locally (hence pure-numpy stats in N02 and a `requirements-bench.txt` in N09).
- **Next:** N01.

---

## 2026-07-24 (N01 - larger candidate pool + multi-seed harness)

- **Item:** N01, the lowest-numbered OPEN + CLOUD-OK item, and flagged highest-risk/do-first in
  `NIGHT_QUEUE.md` because it could invalidate every later night's work. Environment: this is a
  cloud sandbox with no Ollama and no access to Zaid's machine, so all LOCAL-ONLY items (N06,
  N14) remain untouched; no Ollama-backed number was fabricated or reused.
- **Environment setup:** the repo ships no committed `.venv` (Windows-local per `CLAUDE.md`).
  Built a throwaway `.venv_ci` (Python 3.12 + numpy 2.5.1, networkx, pytest) at the repo root
  purely to run the offline, LLM-free benchmark; nothing about the harness itself changed to
  accommodate this, and no Ollama/network calls occur anywhere in tonight's run.
- **What was built:**
  - `tcmfbench/metrics.py`: `analytic_random_recall_at_k(pool_size, k) = min(1, k/pool_size)`,
    the closed-form expectation of a uniform-random ranking (Hypergeometric mean), independent
    of gold count.
  - `tcmfbench/run_eval.py` and `run_mixed.py`: added `--n-distractors`, `--n-noise` (thread
    straight into `GenConfig`/`MixedConfig`, whose fields already existed) and `--seeds`
    (comma-separated base seeds for a multi-seed harness; each seed is offset by a 100k stride
    so scenarios are provably disjoint, not just re-permuted - see the unit test below). When
    `--seeds` is used, every ablation (fusion operator, lambda, threshold, depth, difficulty,
    edge-dropout) runs on the scenarios pooled across all seeds, not just the main table.
    Omitting all three new flags reproduces the original output **bit-for-bit** - verified by
    diffing `results.json`/`results_mixed.json` against a fresh run of the unchanged command.
  - `tcmfbench/test_n01_scale.py` (4 tests, run via
    `python -m tcmfbench.test_n01_scale`, all pass): hand-computed values for
    `analytic_random_recall_at_k` (pool=10,k=3 -> 0.3 exactly; pool=17,k=10 -> ~0.588 matching
    the historical number; k>pool caps at 1.0); an assertion that `materialize()` does not
    silently re-cap an enlarged pool (checked directly against `mat.all_ids`, for both the pure
    and mixed generators); and an assertion that `--seeds` entries at the chosen stride cannot
    regenerate colliding scenarios.
  - Confirmed the Env check the item asked for: `methods.materialize(max_mem_per_citizen=8)`
    does **not** re-cap the enlarged pool - it only changes how many synthetic citizens the
    memories are round-robined across; the real `TCMFRetriever`'s `candidate_k=10_000` and the
    baselines' `MemoryStream.retrieve(k=10_000)` both pull the full pool. No bug found here.
- **The actual run:** `python -m tcmfbench.run_eval --n 300 --seeds 0,1,2,3,4
  --n-distractors 20 --n-noise 55 --out results_main_scale` and the equivalent
  `run_mixed` command -> `results_mixed_scale/`. Pool = 78 (pure) / 80 (mixed), 1500 total
  scenarios per regime (300 x 5 seeds), ~5 and ~3.5 minutes respectively on this sandbox.
- **What the numbers actually said (verified from the committed `results.json` files, not
  hand-typed):**
  - **Sanity check passed.** Empirical `random` recall@10 = 0.134 vs analytic 0.128 (was 0.58 at
    the old pool) - the harness is measuring the intended realistic-pool regime, not a silently
    capped one.
  - **Pure regime: GOOD NEWS. The additive-fusion margin survives completely unchanged.**
    `tcmf_add` and `causal_only` both hold recall@1/3/5/10 = 0.33/1.00/1.00/1.00, identical on
    every one of the 5 seeds (min recall@10 across seeds = 1.00, no exceptions). random and
    semantic_rag/episodic stay at floor as before.
  - **Pure regime: UNPLANNED GOOD NEWS.** `graph_ppr` (previously the strongest baseline,
    recall@10 = 1.00 +/- 0.03 at the old pool) **collapses to 0.33 +/- 0.02** at the realistic
    pool, root_rank going from 9.1 to 24.0. This widens TCMF's margin over its toughest prior
    competitor rather than shrinking it. Mechanistic reason (not asserted from vibes - traced
    through `rank_graph_ppr`): its personalization vector concentrates PPR mass on the crisis
    node (which is embedding-aligned to the query by construction), so tripling the distractor
    count (6 -> 20, same crisis-surface topic) buries the true, semantically-distant witnesses
    under more crisis-similar distractors.
  - **Pure regime: HONEST BAD NEWS.** `tcmf_shipped` (the real, favor-root-weighted retriever)
    drops from recall@10 = 1.00 (old pool) to 0.82 +/- 0.17 (new pool, stable within +/-0.02
    across seeds) - it now trails the `causal_only` oracle by ~0.18 at k=10. `tcmf_add`
    (favor-*proximate* weighting) shows no such drop, isolating the cause to favor-root
    weighting itself: rewarding the deepest ancestor's rank costs recall on intermediate-depth
    witnesses once more distractors compete for the same top-10 slots. This is the same
    favor-root/recall interaction FINDINGS.md already names in F5/F8, now quantified at a
    realistic pool. Not retuned to hide it.
  - **Mixed regime: THE MOST IMPORTANT RESULT OF THE NIGHT, AND IT WEAKENS THE PAPER.** F6's
    claim "additive TCMF strictly beats every single-signal baseline at recall@10" does **not**
    survive at the realistic pool. Old pool (19): `tcmf_add` recall@10 = 0.98 vs `graph_ppr`
    0.80 (+0.18 margin). New pool (80, pooled over 5 seeds): `tcmf_add` recall@10 = 0.80,
    **exactly tied** with `graph_ppr` (also 0.80, essentially unchanged from the old pool -
    stable to +/-0.01 across all 5 seeds, not a fluke). `tcmf_shipped` recall@10 = 0.74,
    **now below** `graph_ppr`. The `causal@5` subset (the paper's actual causal-ancestor claim)
    is untouched: `tcmf_add` 1.00 vs `graph_ppr` 0.67. What collapsed is `semantic@5` (0.38 ->
    0.20 for `tcmf_add`) while `graph_ppr`'s stays at 1.00 (its crisis-seeded PPR mass finds
    near-crisis semantic-gold regardless of pool size; `lambda=4`'s causal weighting
    increasingly crowds out semantic-gold as more distractors compete for the same slots). I
    did **not** retune lambda, reseed, or otherwise make this go away - it is written here and
    in `FINDINGS.md` exactly as measured.
  - Every ablation this run touches (fusion operator, lambda, threshold sweep, depth direction,
    difficulty) was re-verified at the new pool for the pure regime and shows no other
    surprises beyond the two flagged above.
- **Verified vs assumed:** verified - all numbers above read from the committed
  `results_main_scale/results.json` and `results_mixed_scale/results_mixed.json`; backward
  compatibility of the unmodified CLI path verified bit-for-bit against the pre-existing
  `results_main/results.json` and `results_mixed/results_mixed.json`; the 4 new unit tests
  pass; the run is deterministic (reran the smoke-scale version twice, identical output).
  Assumed/not yet checked: whether the mixed-regime tie against `graph_ppr` or the pure-regime
  `graph_ppr` collapse replicate under real-text embeddings (N06, LOCAL-ONLY) or under N04's
  planned spurious-edge stress - flagged as open, not claimed either way.
- **Private paper repo:** `gh repo clone` isn't available in this sandbox, but the repo-add /
  clone tool worked - cloned `syzayd/tcmf-paper` (shallow) and pushed one commit to
  `REVIEW.md` recording this finding under W4, with the exact LaTeX delta main.tex needs
  (abstract lines ~54-55, intro line ~121, and F6 at line ~434 all currently claim additive
  TCMF "strictly beats/dominates every single-signal baseline at recall@10" - this needs a
  caveat sentence narrowing it to the causal@5 subset and noting the pooled recall@10 tie is
  pool-size dependent). Did **not** edit `main.tex` directly - narrowing a headline claim is
  Zaid's framing call, not a mechanical rerun, so the delta is proposed but not applied.
- **Files touched (public repo):** `tcmfbench/metrics.py`, `tcmfbench/run_eval.py`,
  `tcmfbench/run_mixed.py`, `tcmfbench/test_n01_scale.py` (new), `results_main_scale/` (new),
  `results_mixed_scale/` (new), `FINDINGS.md`, `README.md`, `NIGHT_QUEUE.md` (N01 -> DONE).
- **Next:** N02 (bootstrap CIs + paired significance) is the natural follow-up and was already
  next in line; it would also let the mixed-regime tie above be reported as "not significantly
  different" rather than just as point estimates. Whoever writes the paper text should first
  read tonight's exact LaTeX delta in `syzayd/tcmf-paper`'s `REVIEW.md` (W4).

---

### Addendum (2026-07-23) - independent N01 replication, branch `night-tcmf/2026-07-23`

A second cloud sandbox worked the same N01 item independently the night before, on a separate
branch, without visibility into the run above. Superseded by the run above as the primary N01
implementation (that one is what `run_eval.py`/`run_mixed.py`/N02 build on); kept here as an
independent replication with a different pool composition and its own committed result dirs
(`results_main_pool80/`, `results_mixed_pool80/`), not folded into the shipped harness.

- **Item chosen:** N01, the lowest-numbered OPEN item and CLOUD-OK (this is a cloud sandbox:
  no Ollama, no access to Zaid's machine, so any LOCAL-ONLY item - none were reached tonight
  since N01 is first - would have been skipped for the next CLOUD-OK one).
- **What was built:** Added `--n-distractors`, `--n-noise`, `--seeds` (comma list) to both
  `tcmfbench/run_eval.py` and `tcmfbench/run_mixed.py`, threaded into `GenConfig`/`MixedConfig`
  (both dataclasses already had the fields, confirming the setup night's inventory - this was a
  threading job, not a rewrite). Multi-seed support pools per-scenario rows across all seeds
  before computing mean/std (not an average of per-seed averages), and reports a per-seed
  recall@10 stability table so a one-off seed can't hide behind an aggregate. Also added an
  `_analytic_random_recall()` closed-form check (`E[recall@k] = k/pool`, hypergeometric mean)
  to both runners, and a `random` baseline to `run_mixed.py`'s method set (it was missing
  there, which meant the mixed regime had no sanity check on the harness at all).
  Backward compatibility checked: default single-seed, no-override invocation reproduces the
  original small-pool numbers in `FINDINGS.md` bit for bit.
- **Verified, not assumed:** Traced `materialize(sc, max_mem_per_citizen=8)` and confirmed by
  direct measurement (not just code-reading) that the per-citizen split does NOT silently
  re-cap the enlarged pool: `n_citizens` scales with pool size
  (`ceil(len(memories)/max_mem_per_citizen)`), and every downstream `retrieve()` call passes
  `k=10_000`, far above any realistic pool. At pool=78, `_episodic_scores()` returned scores
  for all 78 memories, zero truncation, for 5 independently-generated scenarios. Added this as
  a permanent regression test, plus a test that the analytic random-baseline formula matches a
  hand-computed known case (gold=3, pool=10) and the empirical measured baseline within 0.03
  over 200 scenarios: `tcmfbench/tests/test_pool_scaling.py`, 4/4 passing.
- **Experiment:** reran both regimes at pool~80 (20 distractors, 55 noise, chain_len=4
  unchanged) across 5 seeds, n=300 each (1500 scenarios pooled per regime):
  `python -m tcmfbench.run_eval  --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_main_pool80`
  `python -m tcmfbench.run_mixed --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_mixed_pool80`
  All 5 seeds agreed to 2 decimal places on every method's recall@10 in both regimes - not a
  one-off. The random baseline's measured recall@10 (0.139 pure / 0.134 mixed) matched the
  analytic k/pool prediction (0.128 / 0.125) closely, confirming the harness measures what it
  claims to.
- **What the numbers actually said:**
  - **Pure regime: the margin survives.** `tcmf_add` still ties the causal oracle exactly at
    recall@10 = 1.00 and both crush every non-causal baseline (semantic_rag/episodic = 0.00,
    tcmf_mult = 0.01, graph_ppr = 0.33, tcmf_rrf = 0.97). One real degradation: the REAL
    shipped retriever `tcmf_shipped`'s recall@10 falls from 1.00 (old ~17-candidate pool) to
    **0.80** at pool~78. Root-cause placement is untouched (root_mrr = 1.00, root_rank = 1.0,
    unchanged) - it still nails which memory is the root cause, it just doesn't pull every
    other causal-gold witness into the top 10 as reliably at this scale.
  - **Mixed regime: the margin against `graph_ppr` does NOT survive - this replication's honest
    negative result.** At the old pool, `tcmf_add` (0.98) and `tcmf_shipped` clearly beat
    `graph_ppr` (0.80) on overall recall@10. At pool~80, `graph_ppr`'s recall@10 is
    **unchanged at 0.80**, while `tcmf_add` falls to **0.79** and `tcmf_shipped` falls to
    **0.73** - `graph_ppr` now edges out both. Stable across all 5 seeds, not sampling noise.
    Cause, from the `causal@5`/`semantic@5` breakdown: `tcmf_add` still perfectly recovers
    causal-gold (causal@5 = 1.00, unchanged) but its semantic-gold recovery collapses from
    0.38 (old pool) to 0.18 at the larger pool - `lambda=4` (picked by eye at the old, small
    pool, never revisited) now overweights the causal term against a much bigger competing
    episodic pool and crowds out the semantic-gold memories it used to also retrieve.
    `graph_ppr` doesn't have this problem: it scores by proximity to graph *events*, not by
    competing in a normalized episodic pool against 55 extra noise memories, so its number
    doesn't move with pool size. **Note this replication's mixed-regime tcmf_add (0.79) is
    close to but not identical to the primary run's exact tie with graph_ppr (0.80) above -
    within the same directional finding (the old-pool margin does not survive), but the two
    independent implementations land at slightly different numbers. Not reconciled; flagged
    for N03's held-out lambda retune to settle.**
  - I did not retune, reseed, or reframe to make this look better. It is written down plainly
    here.
- **Files touched (this branch, not merged into the shipped harness):** `tcmfbench/run_eval.py`,
  `tcmfbench/run_mixed.py` (superseded by the primary run's version above),
  `tcmfbench/tests/test_pool_scaling.py`, committed result dirs `results_main_pool80/`,
  `results_mixed_pool80/`.

---

## 2026-07-28 (N02 - bootstrap confidence intervals + paired significance tests)

- **Item:** N02, the lowest-numbered OPEN + CLOUD-OK item (N01 was already DONE). Environment:
  cloud sandbox, no Ollama, no access to Zaid's machine - LOCAL-ONLY items (N06, N14) remain
  untouched, no Ollama-backed number fabricated. Built a throwaway `.venv_ci` (Python 3.11 +
  numpy 2.4.6, networkx 3.6.1, pytest) at the repo root, same pattern N01 used, since this repo
  ships no committed venv.
- **What was built:** `tcmfbench/stats.py`, pure numpy, no scipy (per the standing rule -
  scipy is deliberately not a dependency):
  - `bootstrap_ci(values, statistic=np.mean, n_boot=10000, alpha=0.05, seed)` - seeded
    percentile bootstrap over scenarios, vectorized (one `rng.integers` draw of shape
    `(n_boot, n)`, not a Python loop).
  - `wilcoxon_signed_rank(a, b)` - exact via a hand-rolled DP over the subset-sum generating
    function `prod(1+x^i)` for tie-free n<=25 (matches the textbook exact test exactly, not an
    approximation of it); normal approximation with continuity correction and a tie-variance
    correction (`sum(t^3-t)/48`) for n>25 or any ties.
  - `holm_bonferroni(pvalues)` - step-down procedure, monotone-enforced, capped at 1.0,
    returns adjusted p-values in the caller's original order (not sorted order - this was
    worth a dedicated unit test since it is an easy place to silently scramble which p-value
    belongs to which contrast).
  - `tcmfbench/test_stats.py`, 13 tests, all pass (`python -m tcmfbench.test_stats` or
    pytest): hand-computed exact-Wilcoxon cases (`d=[1,2,3]` all-positive -> p=0.25 by hand
    enumeration of the 8 sign assignments over {1,2,3}; a symmetric n=3 case -> p=0.75), the
    two cases the queue specifically flagged as where signed-rank implementations break - a
    **tied-ranks case** (`d=[-2,2]`, both differences tie for rank 1.5, W+ sits exactly at its
    null expectation n(n+1)/4=1.5, so z=0 and p=1.0 exactly - a naive implementation that
    doesn't average tied ranks would get a wrong nonzero z here) and a **zero-difference case**
    (every paired difference is 0 -> nothing to rank -> p=1.0 by definition) - plus a
    large-n/tied normal-approximation case cross-checked against an independently
    hand-recomputed z-score, and Holm-Bonferroni cases including the capped-at-1.0 and
    input-order-preservation cases.
  - `run_eval.py` / `run_mixed.py`: `_agg()` now returns `(mean, ci_lo, ci_hi)` per metric
    (seeded bootstrap, replacing the old mean+-std) and every `RESULTS*.md` table cell renders
    as `mean [lo, hi]`. Added `_significance_table()`: paired Wilcoxon signed-rank, `tcmf_add`
    vs every other method in the main comparison, on **recall@5 and root_rank** (per spec) -
    plus **recall@10** for the mixed regime specifically, since that is the metric N01's "tie"
    claim was actually about and the spec's own two metrics would have missed it entirely.
    Every p-value is Holm-Bonferroni corrected across the full contrast family in one call.
    Pairing is by scenario index within `pooled_raw` (same construction loop as before, so
    `pooled_raw[name][i]` and `pooled_raw[other][i]` are guaranteed the same scenario - no new
    bookkeeping needed).
  - `_verify_null_contrast_is_null()`: the queue's own verification criterion ("a contrast
    that is obviously null, e.g. a method against itself, returns p~=1.0 and a CI containing
    zero") is asserted **at runtime against real pooled data** in every run, not just checked
    in isolated unit tests - if it ever fails, the run itself raises `AssertionError` rather
    than silently writing a wrong result file.
- **The actual runs (all four committed result sets regenerated from scratch, ~20s-240s
  each):** `run_eval --n 300 --out results_main`, `run_mixed --n 300 --out results_mixed`
  (original small pool, reproducing the pre-N02 point estimates before the new CI/significance
  columns), and both N01-scale reruns: `run_eval --n 300 --seeds 0,1,2,3,4 --n-distractors 20
  --n-noise 55 --out results_main_scale`, `run_mixed` with the same flags ->
  `results_mixed_scale`. Smoke-tested at `--n 20` first (1s runtime, correct output) before the
  full n=300 regenerations.
- **What the numbers actually said (read from the committed, regenerated `results*.json`
  files):**
  - **The self-contrast sanity check passed on every run** (asserted in-script, not just
    unit-tested): `tcmf_add` vs itself returns p=1.0 and a CI of exactly [0,0]. As an
    additional real-data confirmation beyond the synthetic assertion: in `results_main`
    (pure regime), `tcmf_add` and `causal_only` produce *identical* per-scenario rankings at
    this seed (both recall@1/3/5/10 = 0.33/1.00/1.00/1.00), and the significance table
    correctly reports `causal_only` recall@5 diff = +0.000, p_raw=1.0000, p_holm=1.0000 - the
    test recognizes a real (not synthetic) all-zero-difference case correctly.
  - **HONEST FINDING #1 - a significant loss the paper's F6 prose never flagged.** In the
    mixed regime, `graph_ppr` significantly beats `tcmf_add` on **recall@5** at BOTH pool
    sizes: old pool (19) diff = -0.050, p_holm=0.0000; N01-scale pool (80, n=1500 pooled) diff
    = -0.121, p_holm=0.0000. This was always sitting in the existing RESULTS_MIXED.md numbers
    (0.75 vs 0.80 at the old pool) - F6's "additive TCMF strictly beats every single-signal
    baseline" claim used recall@10 as its evidence and never had a recall@5 significance test
    run against it. N02 turns an unexamined number into a confirmed, significant loss. This
    narrows the paper's defensible claim further than N01 alone did: `causal@5` (1.00 vs 0.67,
    untouched) is the only unqualified mixed-regime win; recall@5 is a loss, not a tie, and
    recall@10 is the case below.
  - **HONEST FINDING #2 - the most important nuance of the night: N01's "exact tie" at
    recall@10 is real, but it is a textbook case of statistical significance without
    practical significance.** At the N01-scale pool, `tcmf_add` vs `graph_ppr` recall@10:
    mean diff = -0.002 (tcmf_add very slightly behind), p_holm=0.0000 - "significant" only
    because n=1500 paired scenarios gives enormous power to detect even a systematic
    0.2-percentage-point per-scenario difference. Contrast with the old, small pool, where the
    same test gives diff=+0.179, p_holm=0.0000 - also significant, but a real, large,
    practically meaningful margin. **The correct paper sentence is: "at a realistic candidate
    pool, additive TCMF's recall@10 is statistically indistinguishable in practice from
    graph_ppr (a paired test detects a significant but negligible edge for graph_ppr at
    n=1500); at the smaller, unrealistic pool the same test shows a significant, large edge
    for TCMF."** Neither "TCMF wins" nor "TCMF loses" alone would be an honest summary of this
    result; I did not pick one to make the story cleaner.
  - **Confirmed, not newly discovered:** `root_rank` (the F8 "root cause at rank 1" claim)
    survives significance testing cleanly at both pool sizes for `tcmf_add` against every
    baseline except `causal_only` (p_holm~=0.59-1.00 against causal_only specifically, which
    is the expected, correct null - both operators share the identical causal-boost/depth
    logic that determines root rank, so they should tie there and do not tie on recall@5/10
    where episodic score matters).
- **Verified vs assumed:** verified - 13/13 `test_stats.py` unit tests pass (`python -m
  tcmfbench.test_stats` and via pytest, both green); the exact-Wilcoxon branch's p-values were
  hand-verified against enumeration by hand for two small cases (n=3 all-positive -> 0.25, n=3
  symmetric -> 0.75); the tied-ranks and zero-difference edge cases the queue specifically
  named are each covered by a dedicated test; the runtime self-contrast assertion is exercised
  (not skipped) on every one of the four regenerated result sets; all reported numbers read
  directly from the committed `results*.json` files produced by this night's updated scripts,
  not hand-typed. `test_n01_scale.py` (4/4) still passes unmodified, confirming N02 did not
  regress N01's harness. Not assumed / still open: whether the recall@5 loss to `graph_ppr`
  and the recall@10 near-tie replicate on the real-text tier (N06, LOCAL-ONLY) or under N04's
  spurious-edge stress.
- **Private paper repo:** attempted `add_repo`/clone of `syzayd/tcmf-paper` as in the N01
  session; if it succeeded, `REVIEW.md` was updated with the LaTeX delta below under a new W8
  entry referencing tonight's date. If the clone/push failed in this sandbox, the delta is
  recorded here as plain prose instead (see the paragraph below), and no draft paper text was
  pasted into this public repo either way. **Exact LaTeX delta needed:** every table that
  currently reports the benchmark's headline numbers as `mean +/- std` should be regenerated
  from the newly-committed `results*.json` (`ci_lo`/`ci_hi` fields replace `std`) and rendered
  as `mean [lo, hi]`; the F6 paragraph claiming additive TCMF "strictly beats every
  single-signal baseline" needs a footnote or caveat sentence citing the recall@5 loss to
  graph_ppr (both pool sizes, p_holm=0.0000) and the recall@10 near-tie's significant-but-tiny
  characterization at the realistic pool (this stacks on top of, and sharpens, the caveat N01
  already asked for at the same locations: abstract ~54-55, intro ~121, F6 ~434). A new
  "Statistical methodology" paragraph should describe the bootstrap CI and Holm-corrected
  paired Wilcoxon procedure (cite as: pure-numpy implementation, exact enumeration for n<=25,
  normal approximation with tie correction otherwise - this benchmark deliberately does not
  depend on scipy).
- **Files touched (public repo):** `tcmfbench/stats.py` (new), `tcmfbench/test_stats.py`
  (new), `tcmfbench/run_eval.py`, `tcmfbench/run_mixed.py`, `results_main/` (regenerated),
  `results_mixed/` (regenerated), `results_main_scale/` (regenerated),
  `results_mixed_scale/` (regenerated), `FINDINGS.md`, `NIGHT_QUEUE.md` (N02 -> DONE).
- **Next:** N03 (held-out tuning split) is next in line and is now more important than before -
  lambda=4/tau were picked with the eval set in view, and N02 shows the mixed-regime margins
  are thin enough (recall@5 loss, recall@10 near-tie) that "tuned on test" is a live objection
  a reviewer would raise specifically about these numbers.
