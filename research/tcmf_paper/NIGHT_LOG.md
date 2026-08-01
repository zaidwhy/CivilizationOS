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

---

## 2026-07-30 (N03 - held-out tuning split)

- **Item:** N03, the lowest-numbered OPEN + CLOUD-OK item (N01, N02 already DONE; N04-N14 all
  still OPEN but N03 is lower-numbered). Environment: cloud sandbox, no Ollama, no access to
  Zaid's machine - LOCAL-ONLY items (N06, N14) remain untouched, no Ollama-backed number
  fabricated. Built a throwaway `.venv_ci` (Python 3.11 + numpy 2.4.6, networkx 3.6.1, pytest)
  at the repo root, same pattern N01/N02 used, since this repo ships no committed venv.
- **What was built:** `tcmfbench/run_tuned.py`, importing (not duplicating) `run_eval.py`'s and
  `run_mixed.py`'s existing `_table`/`_significance_table`/`_verify_null_contrast_is_null`/
  `_agg`/`main_methods`/`MAIN_ORDER`/`ORDER` helpers:
  - Partitions the N01/N02 5-seed protocol (0-4, `SEED_STRIDE=100_000`) into a **fixed**,
    disjoint TUNE split (seeds 0,1 = 40%) and TEST split (seeds 2,3,4 = 60%), per spec. Fixed
    means hardcoded, not re-drawn per invocation - a later night cannot quietly repartition to
    get a better-looking tune score.
  - Sweeps 5 operators with an **equal budget of 5 candidate values each** (stated in-code as
    `SWEEP_BUDGET = 5`, asserted at import time): `tcmf_add` lambda, `tcmf_mult` lambda, RRF
    `c`, `causal_only` tau, `graph_ppr` alpha. Each is swept independently (one hyperparameter
    at a time, everything else held at the main comparison table's own default), selected by
    mean recall@5 on TUNE data only - never the test split. Selection uses `select_best()`, a
    standalone function with an explicit tie-break rule (smallest candidate value wins a tie -
    the exact case a naive `max(scores, key=scores.get)` gets wrong, since Python's `max` keeps
    the first-encountered max on ties, which is dict-insertion-order dependent, not
    value-dependent; unit-tested with insertion order deliberately set to the losing order).
  - Runs the full main-comparison table (bootstrap CIs, paired Wilcoxon vs `tcmf_add`,
    Holm-Bonferroni correction, and N02's runtime null-contrast assertion) on the TEST split
    only, with the tune-selected hyperparameters plugged in for the 5 swept operators and every
    other method (`random`, `recency`, `semantic_rag`, `episodic`, `tcmf_shipped`) left at its
    existing default.
  - Adds an ordering-check that loads the already-committed `results_main_scale/results.json`
    and `results_mixed_scale/results_mixed.json` (N01's pooled-5-seed numbers) directly - not
    hand-retyped - and compares their recall@10 ranking against tonight's TEST-only ranking,
    per the item's own verify criterion ("confirm the headline ordering is unchanged from N01;
    if it moves, that is the honest result").
  - `tcmfbench/test_n03_tune_split.py`, 8 tests, all pass (`python -m
    tcmfbench.test_n03_tune_split` and via pytest): the tune/test split is disjoint, covers
    exactly `{0,1,2,3,4}`, and is exactly 40%/60%; every operator's grid has exactly
    `SWEEP_BUDGET=5` candidates; `select_best` picks the argmax and, on a synthetic tie,
    deterministically picks the smaller value regardless of dict insertion order; the tune/test
    scenario pools are disjoint (reusing N01's stride-collision check, applied to the specific
    `TUNE_SEEDS`/`TEST_SEEDS` this script uses); a small (n=5/seed) end-to-end smoke test of
    the full sweep-then-test pipeline runs to completion and writes a well-formed result file.
- **The actual runs** (default pool matches N01's realistic pool: `--n-distractors 20
  --n-noise 55`, the script's own default, stated explicitly so a future run cannot silently
  fall back to the old small pool): `python -m tcmfbench.run_tuned --regime pure --n 300 --out
  results_main_tuned` (~1m19s: 600 tune scenarios x 25 sweep evaluations + 900 test scenarios x
  10 methods) and `--regime mixed --n 300 --out results_mixed_tuned` (~1m18s). Full tables:
  `results_main_tuned/RESULTS_TUNED.md`, `results_mixed_tuned/RESULTS_TUNED.md`.
- **What the numbers actually said (read from the committed `results_tuned.json` files, not
  hand-typed):**
  - **HEADLINE RESULT 1 - the mixed-regime `tcmf_add` vs `graph_ppr` recall@10 near-tie
    survives an honest tune/test split; it was never test-set peeking.** On the TEST split
    only (900 scenarios never seen during hyperparameter selection): `tcmf_add` recall@10 =
    0.80 [0.79, 0.81], `graph_ppr` = 0.80 [0.80, 0.80], paired diff = -0.002, p_holm = 0.0000 -
    matching N02's pooled-data finding almost exactly. The recall@5 loss to `graph_ppr` also
    reproduces on TEST-only data: diff = -0.116, p_holm = 0.0000 (N02's pooled number was
    -0.121). This answers the open question both N01 and N02 explicitly flagged as
    unresolved: the tie/loss holds up even when lambda is selected on data disjoint from the
    number being reported, so it is a real property of the fusion regime at this pool size, not
    an artifact of eyeballing the eval set while picking lambda=4. `causal@5` remains the
    dominant, unaffected TCMF number (1.00 vs `graph_ppr`'s 0.67).
  - **HEADLINE RESULT 2 - HONEST, PARTIALLY GOOD NEWS, and a fairness bug in every prior
    night's protocol.** N01's "pure-regime `graph_ppr` collapses to 0.33 at the realistic pool"
    finding was measured at `graph_ppr`'s never-tuned default alpha=0.85. A fair tune-only
    sweep of alpha alone (same 5-candidate budget every other operator got) recovers
    `graph_ppr` to **0.67** recall@10 in the pure regime - tune-set recall@5 rose monotonically
    with alpha (0.00 -> 0.00 -> 0.07 -> 0.33 -> 0.67 at alpha 0.50/0.65/0.75/0.85/0.95).
    `tcmf_add`/`causal_only` still fully dominate (1.00 vs 0.67 - unchanged, still a complete
    win), so F1-F8's qualitative claim is untouched, but the specific "collapses to 0.33"
    number needs a caveat: every earlier night swept TCMF's own hyperparameters (lambda,
    threshold, depth direction) but never gave the strongest baseline the same tuning
    fairness. In the mixed regime alpha=0.85 was already TUNE-optimal, so this effect is
    pure-regime-specific; the mixed-regime graph_ppr number is unaffected.
  - **HEADLINE RESULT 3 - smaller nuance, still worth flagging plainly.** Tuning `tcmf_mult`'s
    own lambda properly (2.4, selected on TUNE data, vs the arbitrary untuned default 0.6 used
    everywhere in F1-F8) more than doubles its pure-regime recall@10 from ~0.00-0.02 to 0.54 -
    enough to overtake `random`/`recency` in the headline ranking, though it stays far below
    `causal_only`/`tcmf_add` (1.00) and `tcmf_shipped` (0.83). F3's qualitative claim ("the
    shipped multiplicative fusion suppresses the causal signal") is untouched, but the specific
    near-zero magnitude quoted for `tcmf_mult` throughout the paper was measured at an unfairly
    low, never-swept lambda - a properly tuned multiplicative baseline is a meaningfully
    stronger (if still clearly losing) opponent than currently credited.
  - **Ordering check (the item's own verify criterion): CHANGED from N01 in both regimes, but
    only in the tail, never among the methods the paper's claims are about.** Pure regime:
    `tcmf_mult` (now properly tuned) moves from rank 8 to rank 6, past `random`/`recency` (which
    have no tunable hyperparameter here and don't move). Mixed regime: `tcmf_mult` moves from
    rank 7 to rank 6, past `semantic_rag`. In both regimes, ranks 1-5 - `causal_only`,
    `graph_ppr`, `tcmf_add`, `tcmf_shipped`, `tcmf_rrf`, the methods every paper claim is
    actually about - keep the exact same order as N01. I did not retune, reseed, or reframe
    any of the three findings above to make them look better; all three are written down
    plainly, including the one that is unambiguously good news for a competing baseline.
  - **Discovered, not fixed tonight (pre-existing, out of scope for this item):**
    `tcmfbench/tests/test_pool_scaling.py` (from the earlier independent N01-replication
    addendum branch, not the primary harness) fails to import - it references a
    `run_eval._analytic_random_recall` helper that was never part of the shipped
    implementation (the primary harness uses `metrics.analytic_random_recall_at_k`, covered by
    `test_n01_scale.py`). Confirmed this predates tonight's change: reproduces identically with
    only `origin/main`'s files present, before any of tonight's new files existed. Not silently
    patched - flagged here since fixing another night's orphaned test file was not this item's
    job.
- **Verified vs assumed:** verified - 8/8 `test_n03_tune_split.py` unit tests pass (direct
  invocation and via pytest); `test_n01_scale.py` (4/4) and `test_stats.py` (13/13) still pass
  unmodified, confirming N03 did not regress N01/N02's harness; both regimes' TEST-split
  null-contrast assertion (`tcmf_add` vs itself: p=1.0, CI=[0,0]) passed against real run data,
  not just in isolated unit tests; pool sizes read from `results_tuned.json` match N01 exactly
  (78 pure / 80 mixed); the ordering-check table is generated by loading the committed N01
  result JSON files programmatically, not by re-typing numbers. Not assumed / still open:
  whether this tune/test split's conclusions replicate on the real-text tier (N06,
  LOCAL-ONLY) or under N04's planned spurious-edge stress.
- **Private paper repo:** attempted the same `add_repo`/clone of `syzayd/tcmf-paper` as prior
  nights; if it succeeded, `REVIEW.md` got a new entry under W5 with the delta below. If the
  clone/push failed in this sandbox, the delta is recorded here as plain prose instead, and no
  draft paper text was pasted into this public repo either way. **Exact LaTeX delta needed:** a
  new "Held-out tuning" paragraph describing the fixed 40/60 seed-disjoint tune/test split and
  the 5-candidate equal-budget sweep per operator; the F6/N01/N02 caveat sentences (abstract
  ~54-55, intro ~121, F6 ~434) should be strengthened from "this margin does not survive at a
  realistic pool" to "this margin does not survive at a realistic pool, confirmed under a
  held-out tune/test split (not test-set peeking)"; a new caveat near the N01 graph_ppr
  discussion noting the 0.33 collapse number was measured at an untuned graph_ppr alpha and
  recovers to 0.67 under fair tuning (still fully dominated by tcmf_add/causal_only, so the
  headline claim is unaffected, but the specific magnitude needs the correction); and a similar
  one-sentence caveat on tcmf_mult's near-zero baseline magnitude (0.00-0.02 quoted in F3 was at
  an untuned lambda=0.6; a tuned tcmf_mult reaches 0.54 recall@10, still far below tcmf_add).
- **Files touched (public repo):** `tcmfbench/run_tuned.py` (new),
  `tcmfbench/test_n03_tune_split.py` (new), `results_main_tuned/` (new),
  `results_mixed_tuned/` (new), `FINDINGS.md`, `README.md`, `NIGHT_QUEUE.md` (N03 -> DONE).
- **Next:** N04 (spurious-edge robustness) is next in line - only missing edges have been
  stressed so far (N01's dropout curve); wrong edges (a false ancestor injecting a confident
  wrong boost) are the more dangerous failure mode and reviewers will ask for exactly this.

---

## 2026-07-31 (N04 - spurious-edge robustness)

- **Item:** N04, the lowest-numbered OPEN + CLOUD-OK item (N01-N03 already DONE). Environment:
  cloud sandbox, no Ollama, no access to Zaid's machine - LOCAL-ONLY items (N06, N14) remain
  untouched, no Ollama-backed number fabricated. Built a throwaway `.venv_ci` (Python 3.11 +
  numpy 2.4.6, networkx 3.6.1, pytest) at the repo root, same pattern every prior night used,
  since this repo ships no committed venv.
- **What was built:**
  - `tcmfbench/mixed.py`: `MixedConfig.spurious_edge_rate` (default 0.0). With probability p per
    scenario, injects ONE fabricated ancestor event aligned to the crisis SURFACE topic (the
    same topic distractors and semantic-gold already share), linked directly into the crisis
    (`edge = (spurious_event.id, crisis.id)`) - a genuine BFS-predecessor edge in the causal
    graph, not the institution-scoped weak-ancestor fallback, so even the "clean" true-ancestor
    set is fooled by it. The injection is placed AFTER every other random draw in
    `generate_mixed` (query embedding, all memories, the shuffle) and gated behind
    `spurious_edge_rate > 0.0`, so a default (0.0) run consumes zero extra randomness and is
    byte-for-byte identical to a scenario generated before this field existed - this is the
    mechanism that lets the p=0 point of tonight's curve reproduce N01 exactly, not a
    coincidence of the numbers looking similar.
  - `tcmfbench/metrics.py`: `any_in_top_k(ranked, targets, k)` - 1.0 if any id in `targets`
    appears in the top-k, 0.0 otherwise, NaN if `targets` is empty (matching `recall_at_k`'s
    existing NaN convention so it drops out of any mean the same way).
  - `tcmfbench/methods.py`: `distractor_ids(mat)` - the set of memory ids labeled `distractor`,
    for scoring precision-side damage.
  - `tcmfbench/run_spurious.py` (new script, mirrors N03's `run_tuned.py` precedent of a
    dedicated file importing existing infra rather than editing `run_mixed.py` in place):
    sweeps `spurious_edge_rate` in {0, 0.05, 0.1, 0.2, 0.4} at `edge_dropout=0` (full N01-scale
    pool: `--n-distractors 20 --n-noise 55`, 5 seeds, n=300/seed = 1500 scenarios/rate) across 5
    methods (semantic_rag, causal_only, graph_ppr, tcmf_add, tcmf_shipped), reporting
    recall@10 and the new `distractor_top5` precision metric with bootstrap CIs (reusing
    `stats.bootstrap_ci` and `run_mixed`'s seed-stride contract). Also runs a coarser 2-D grid
    (`edge_dropout` in {0, 0.2, 0.4} x the same 5 spurious rates, n=100/seed) for the 3 methods
    F7's existing dropout curve already reports, per the item's own "coarse resolution"
    instruction. **The script asserts its own p=0 recall@10 against the committed
    `results_mixed_scale/results_mixed.json` to machine precision before writing any output** -
    this is the item's own verify criterion ("at p=0 the numbers reproduce N01 exactly"), checked
    at runtime, not eyeballed after the fact.
  - `tcmfbench/test_n04_spurious.py` (8 tests, all pass via `python -m
    tcmfbench.test_n04_spurious` or pytest): rate=0.0 injects nothing and is deterministic
    (byte-identical scenario across two calls, and identical whether `spurious_edge_rate=0.0` is
    passed explicitly or omitted - the exact invariant every pre-N04 script relies on); rate=1.0
    always injects exactly one spurious event + edge, deterministically given the seed; the
    injected event, after `materialize()`, is confirmed a genuine BFS predecessor at depth 1 (not
    just asserted - computed via `mat.graph.predecessors`); the spurious event's topic matches
    the crisis surface topic and never a real ancestor's topic; `any_in_top_k` against 5
    hand-computed cases (hit, miss, empty-targets NaN); `distractor_ids` count matches
    `cfg.n_distractors` exactly and is disjoint from gold. Full suite (`test_n01_scale.py`
    4/4, `test_stats.py` 13/13, `test_n03_tune_split.py` 8/8, `test_n04_spurious.py` 8/8 = 33/33)
    reruns clean, confirming N04 did not regress anything.
- **The actual run:** `python -m tcmfbench.run_spurious --n 300 --grid-n 100 --out
  results_spurious` - ~3m54s on this sandbox (smoke-tested at `--n 10 --grid-n 5` first, ~8s,
  correct shape, before the full run).
- **What the numbers actually said (read from the committed `results_spurious/
  results_spurious.json`, not hand-typed):**
  - **p=0 reproducibility: VERIFIED bit-for-bit, asserted in-script (max diff 0.00e+00 against
    `results_mixed_scale/results_mixed.json`'s semantic_rag/causal_only/tcmf_add recall@10).**
    The spurious-edge knob changes nothing when left at its default, exactly as designed.
  - **Headline 1 - recall degrades monotonically but no crossover in the tested range.** At
    dropout=0, `tcmf_add` recall@10 falls from 0.80 [0.79, 0.81] (p=0) to 0.71 [0.71, 0.72]
    (p=0.4) - a real, monotone ~11-point loss - but never drops below `semantic_rag`'s flat 0.40
    floor. The item's own verify criterion asks to "report the p at which tcmf_add drops below
    semantic_rag" - the honest answer is **it did not, anywhere in {0, 0.05, 0.1, 0.2, 0.4}**; I
    did not extend the range to force a crossover to appear, and the paper must say "no
    crossover observed up to p=0.4," not "TCMF is immune to this attack."
  - **Headline 2 - an unplanned, mechanistically-verified finding: the favor-root fix (shipped
    for the unrelated F5 root-rank reason) is incidentally more robust to THIS specific attack
    than the favor-proximate operator-study defaults, and I traced why rather than asserting it
    from the curve shape.** `graph_ppr` degrades most (0.80 -> 0.63 recall@10, p=0 -> p=0.4);
    `tcmf_add`/`causal_only` (favor-proximate) degrade next (0.80 -> 0.71, 0.64 -> 0.63);
    `tcmf_shipped` (favor-root, the REAL retriever) is flat-to-slightly-up (0.74 -> 0.76).
    Directly inspected a materialized scenario with a forced injection (seed 0,
    `spurious_edge_rate=1.0`): the ancestor-depth map is
    `{"e2": 1, "spurious0": 1, "e1": 2, "e0": 3}`, `max_depth=3` - the false edge, fabricated
    straight into the crisis, is ALWAYS the shallowest possible BFS depth (1), tied with the
    true direct cause. Favor-proximate weighting gives depth-1 its maximum weight (1.0 - exactly
    what a direct false edge needs to do maximum damage); favor-root weighting gives that same
    depth-1 edge its minimum weight (0.33, vs the true root cause's 1.0). **Scope caveat, stated
    plainly rather than overclaimed: this only tests a false DIRECT-cause edge. A fabricated
    edge disguised as pointing deep in the chain (a fake root cause) would land at HIGH depth and
    could hit favor-root's highest-weight band instead - untested this session, and needed
    before claiming favor-root robustness to false ancestors in general rather than to this one
    edge shape.**
  - **Headline 3 - HONEST, PARTIALLY NEGATIVE METHODOLOGICAL FINDING: the precision metric
    mostly sits at ceiling before the experiment even starts, so it cannot show what it was built
    to show for most methods.** At p=0 (zero spurious edges), P(a distractor is in the top-5) is
    already 1.00 for `semantic_rag`, 1.00 for `graph_ppr`, 0.98 [0.97, 0.99] for `tcmf_add`, 0.99
    [0.98, 0.99] for `tcmf_shipped` - a pre-existing property of an 81-item pool with 20
    distractors competing for whatever top-5 slots recall@5 doesn't perfectly fill, unrelated to
    N04's manipulation. Only `causal_only` starts low enough (0.46 [0.43, 0.48]) to show a clear
    signal, rising to 0.68 [0.66, 0.71] at p=0.4 - a real, monotone, well-verified effect, but
    only for the one method where the metric wasn't already saturated. For `tcmf_add`/
    `tcmf_shipped`/`graph_ppr`, tonight's binary any-in-top-5 metric cannot separate "the
    spurious edge promoted a distractor" from "a distractor was already going to be there
    regardless." I did not swap in a different metric to make this look better - it is recorded
    here as an honest gap: a count-of-distractors-in-top-5 metric would very likely show
    gradation where the any-based one is saturated, and is the natural next step, not built
    tonight.
  - **2-D grid (dropout x spurious):** the two knobs' effects look roughly additive at this
    coarse resolution (n=100/seed) - e.g. `tcmf_add` recall@10 at dropout=0.2 barely moves across
    spurious rates (0.60 -> 0.58), while dropout alone (F7) already explains most of the drop
    from the dropout=0 row; no strong interaction term is visible at this resolution, but n=100
    (vs the curve's n=300) is noisier and a finer grid was out of scope tonight.
- **Verified vs assumed:** verified - `test_n04_spurious.py` (8/8) and the full existing suite
  (33/33 total) pass; the p=0 bit-for-bit match is asserted at runtime by the script itself
  (would raise `AssertionError`, not silently diverge - checked by construction, since the run
  completed and wrote output); the depth-1/max_depth=3 mechanism behind Headline 2 was computed
  directly against a real materialized scenario (shown above), not inferred from the curve shape
  alone; all reported numbers read from the committed `results_spurious/results_spurious.json`,
  not hand-typed. Not assumed / still open: whether any of this replicates on the real-text tier
  (N06, LOCAL-ONLY, still unreached); whether a deep-targeted false edge reverses the Headline 2
  finding; whether a count-based precision metric shows gradation the any-based one cannot -
  all three flagged as open questions, not answered by tonight's run.
- **Private paper repo:** attempted `add_repo`/clone of `syzayd/tcmf-paper` as prior nights did;
  see the tool-call outcome recorded right after this entry for whether it succeeded. **Exact
  LaTeX delta needed regardless:** a new "Spurious-edge robustness" paragraph (pairs with the
  existing F7 missing-edge paragraph) reporting the graceful recall degradation and the absence
  of an observed crossover up to p=0.4; a caveat sentence on the favor-root robustness finding
  narrowing it to false DIRECT-cause edges specifically (not false ancestors in general); and an
  explicit methods-limitations sentence noting the precision (distractor-in-top-5) metric is
  near-ceiling for every method except the causal-only oracle, so it could only cleanly evidence
  the effect for that one method - do not claim the precision experiment shows damage for
  tcmf_add/tcmf_shipped/graph_ppr specifically, only for causal_only.
- **Files touched (public repo):** `tcmfbench/mixed.py`, `tcmfbench/metrics.py`,
  `tcmfbench/methods.py`, `tcmfbench/run_spurious.py` (new), `tcmfbench/test_n04_spurious.py`
  (new), `results_spurious/` (new), `FINDINGS.md`, `README.md`, `NIGHT_QUEUE.md` (N04 -> DONE).
- **Next:** N05 (second-domain corpus, authoring only, no embedding) is next in line and is
  CLOUD-OK; N06 (the embedding/run of that corpus) stays LOCAL-ONLY until it can run against
  Zaid's Ollama.

## 2026-08-01 (N15 - formal proposition for the fusion-operator effect)

- **Item:** N15, a NEW item, not the lowest-numbered OPEN one. Chosen deliberately: N05 is next
  in line and the nightly cloud routine takes it tonight, so working it here would have
  collided the way the two competing N01 branches did. N15 came out of an external reviewer
  pass Zaid ran through ChatGPT (scorecard: novelty 8, technical quality 9, experimental design
  9, writing 8.5, reproducibility 9, practical impact 8.5, overall 8.5/10; verdict "accept for
  many workshops, borderline for very selective conferences"). Its top recommendation was the
  one thing the 14-night queue had no item for at all: a theorem. Worked locally by Opus, not
  by the routine.
- **What shipped:** `tcmfbench/theory.py` (the propositions as executable predicates),
  `tcmfbench/test_theory.py` (17 tests, all passing), `tcmfbench/run_theory.py` +
  `results_theory/` (regenerable table), `THEORY.md` (statements, proofs, measured numbers,
  scope limits, and the LaTeX delta the private repo needs).
- **The result.** Both operators' pairwise margins are affine in lambda. For multiplicative
  fusion the slope is `e(i)b(i) - e(j)b(j)`, so the crossing point depends on the episodic
  scores and admits **no bound in terms of the causal margin** - it diverges as
  `e(i)/e(j)` approaches `b(j)/b(i)` (Prop 1). For additive fusion the slope is the causal
  margin itself and min-max normalisation caps the episodic deficit at 1, so
  `lam > 1/(b(r) - b(d))` suffices **regardless of the episodic scores** (Prop 2). A lambda
  sweep on the multiplicative form interpolates from the `e` ordering to the `e*b` ordering, so
  the causal ordering is not on its path (Prop 3) - which is the formal version of the flat
  low-lambda ablation and turns the W2 "you just fixed your own bug" answer into a proof.
- **Measured (`results_theory/`, 10 seeds, pool 80):** the lambda multiplicative fusion needs
  swings **3.0x** across seeds (3.11 to 9.26) plus one seed no lambda solves; additive's swings
  **1.10x** (3.32 to 3.64). The shipped multiplicative default was 0.6, i.e. 5x to 15x below
  requirement, which is the quantitative explanation of the measured recall@5 = 0.02; and the
  empirically-best multiplicative value of 8 (REVIEW.md W5) is simply the smallest round value
  clearing most seeds' crossing points. The shipped additive `lam = 4` clears the Prop 2 bound
  on every solvable seed, so that hyperparameter is now *explained* rather than fitted.
- **HONEST SCOPE LIMIT, and it cut down my first framing.** I started from the reviewer's
  suggested proposition ("if the episodic score approaches zero, multiplicative fusion cannot
  recover rank"). Measuring it killed it: outright impossibility happens for **1 of 200**
  root-cause/distractor pairs, and in that one case the distractor out-boosts the root cause,
  so additive fusion cannot promote it either. That is a **boost-function** defect (threshold
  and depth weighting), upstream of the fusion, which no operator choice addresses. The paper's
  claim is therefore "additive admits one scenario-independent lambda, multiplicative does not"
  and NOT "multiplicative can never retrieve the root cause" - the strong version is false on
  this benchmark and a reviewer with the harness would find it in an afternoon. A test pins the
  1-in-200 rate so the claim cannot drift back.
- **Unrelated defect found and fixed:** `tcmfbench/tests/test_pool_scaling.py` imported
  `run_eval._analytic_random_recall`, which does not exist, so **`pytest` could not collect the
  benchmark suite at all** - it died at collection, meaning the test suite had been unrunnable
  since 2026-07-24. Cause: the duplicate-N01 collision. PR #4 landed
  `metrics.analytic_random_recall_at_k` while PR #3 landed a test written against its own
  never-merged helper. Ported the test to the surviving API and kept its unique coverage (the
  episodic-score truncation guard, which is the exact invariant N01 called load-bearing, and
  the empirical-vs-analytic random-baseline check). Suite now collects and passes: **53
  benchmark tests, 70 API tests.**
- **Verified vs assumed:** verified - all 17 theory tests pass against the SHIPPED rankers
  (`rank_tcmf_multiplicative` / `rank_tcmf_additive`) on real generated scenarios, not against a
  reimplementation; the lambda-to-infinity ordering prediction matches the real ranker exactly
  on every seed tested; the table in THEORY.md is regenerated by `run_theory.py`, not typed by
  hand; both suites run green. Assumed/not yet checked: the analysis is **pairwise** and says
  nothing directly about recall@k; it has not been re-measured under real-text embeddings
  (N06), under spurious edges (N04's grid), or at the N16 pool sizes.
- **Queue changes:** N15 added and marked DONE. N16 (scale to 1000+ memories, multi-crisis
  mode) and N17 (TCMFBench as a standalone contribution with a public API) added as OPEN from
  the same review. N08 amended: the review named REMem, MAGMA, HINDSIGHT and an "event-causal
  RAG" line as recent neighbours, all reported second-hand, so N08 must now verify or explicitly
  record each as non-existent rather than cite it.
- **Files touched (public repo):** `tcmfbench/theory.py` (new), `tcmfbench/test_theory.py`
  (new), `tcmfbench/run_theory.py` (new), `results_theory/` (new), `THEORY.md` (new),
  `tcmfbench/tests/test_pool_scaling.py` (fixed import), `NIGHT_QUEUE.md`, `NIGHT_LOG.md`.
- **Private paper repo:** not touched. The LaTeX delta is written out at the end of `THEORY.md`
  instead - a new "Why the operator decides" subsection, the abstract/intro claim swap to the
  scenario-independent-lambda phrasing that survives N01's pool-size finding, the `lam = 4`
  justification for W5, and the boost-function scope limit for the limitations section.
  Narrowing a headline claim is Zaid's framing call, so it is proposed, not applied.
- **Next:** N05 for the routine tonight. For Zaid: the framing decision the review raised and
  this item sharpens - position the paper as an empirical systems paper that isolates a failure
  mode ("we show the fusion operator, not the graph, is the determining factor") rather than as
  a new retrieval algorithm.

## 2026-08-01 (N08 - citation verification + related-work differentiation)

- **Item:** N08, taken in the same local session as N15 (again avoiding N05, which the routine
  takes tonight). This is the standing "never ship a citation from memory" gate, and it became
  urgent because the external review handed Zaid four recent system names second-hand.
- **Method:** every arXiv ID fetched from its canonical `arxiv.org/abs` page and the title,
  author list and year read off the page. No ID accepted from recall, including for works I
  was confident about.
- **Existing bib: 7 of 8 entries correct, 1 wrong.** Generative Agents (2304.03442), MemGPT
  (2310.08560), HippoRAG (2405.14831), RAG (2005.11401) and Ethayarajh (1909.00512) all check
  out exactly. **GraphRAG (2404.16130) had an incomplete author list** - missing Dasha
  Metropolitansky and Robert Osazuwa Ness. Fixed. (The two pre-2010 IR entries, Cormack RRF and
  Fox-Shaw CombSUM, are not arXiv works and were left as-is.)
- **The four second-hand names all exist, but one is a trap.** REMem = arXiv:2602.13530,
  Feb 2026, and notably it is from the HippoRAG group (Shu, Jimenez Gutierrez, Su). MAGMA =
  arXiv:2601.03236, ACL 2026 long paper. HINDSIGHT = arXiv:2512.12818 (Vectorize.io).
  **"Event-Causal RAG" (arXiv:2605.06185) exists but is a long-VIDEO reasoning framework, not
  agent memory** - citing it would have signalled a related-work section assembled by keyword
  rather than read. Deliberately excluded, with the reason recorded in the bib header so nobody
  re-adds it later.
- **Novelty check, the part N08 exists for. TCMF survives, and MAGMA turns out to help.** MAGMA
  is the closest neighbour found: it really does carry a causal graph, one of four. But (a) it
  traverses all four graphs with a uniform beam search plus per-hop decay, so there is no
  ancestor set and no ancestor depth - it does not do backward reachability from the current
  event; and (b) its scoring function is `exp(l1*phi + l2*sim)`, which is **additive in the
  exponent** and therefore order-equivalent to additive fusion. So a strong concurrent ACL 2026
  system independently landed on the operator Prop 2 says is the safe one, without commenting on
  the choice. That is corroboration, not a scoop. Worth noting for the rebuttal: `exp(a+b) =
  exp(a)exp(b)` is multiplicative in its factors, and is precisely NOT the Prop 1 failure mode -
  what fails is multiplying raw unnormalized scores, not anything writable as a product.
- **Two neighbours found that neither the paper nor the review had named:** CausalRAG
  (arXiv:2503.19878, Findings of ACL 2025) and E2RAG "Respecting Temporal-Causal Consistency"
  (arXiv:2506.05939). Both put causal structure into RAG, both target corpus QA rather than an
  acting agent's episodic memory, and neither studies the fusion operator. Both now cited.
- **Second Method-section error found and fixed** (the first was Eq. 1 in the N15 entry above).
  Related Work described the Generative Agents salience score as
  `relevance x recency x importance`. Park et al. use a weighted **sum** with all alpha = 1,
  verified. So the draft had the product form in two places and both were wrong. Silver lining
  recorded in the draft: that score is very widely reproduced as a product in the wild, which is
  weak but real evidence for W2's "multiplicative is the form practitioners reach for by
  default" argument.
- **Verified vs assumed:** verified - all IDs against arxiv.org on 2026-08-01; MAGMA's scoring
  formula and traversal read from the paper's HTML, not the abstract; the Generative Agents sum
  form cross-checked. `validate.py` reports braces, environments, cross-references and citation
  keys all clean, so every new `\citep` resolves. Assumed/not checked: **the draft has not been
  compiled** - there is no TeX toolchain on this machine, so the new `amsthm` environments and
  the 4-column related-work table are structurally validated but not rendered. Someone with
  LaTeX must build it before submission. Three added entries (Zep, A-MEM, Mem0) still need full
  author lists off their PDFs.
- **Files touched (private repo `syzayd/tcmf-paper`):** `references.bib` (header rewritten with
  verification status, GraphRAG fixed, 8 entries added), `main.tex` (concurrent-systems
  paragraph rewritten, causality-in-retrieval paragraph added, MAGMA paragraph added,
  `tab:related` differentiation table added, Generative Agents score corrected).
- **Files touched (public repo):** `NIGHT_QUEUE.md` (N08 -> DONE with residual), `NIGHT_LOG.md`.
- **Next:** N05 for the routine tonight. N09-N11 (figures) need matplotlib, not installed
  locally yet.

## 2026-08-01 (N18 - does the regime occur in public data?)

- **Item:** N18, a NEW item, added because a strategic question ("is this worth turning into a
  real paper?") reduced to a technical one the whole queue could not answer: every result in
  this benchmark sits on scenarios Zaid authored, so "is the regime real, or did you build a
  simulator that exhibits it?" had no evidence either way. Not a queue night; done locally.
- **First, the constraint that shapes everything else: neither candidate public benchmark ships
  a causal graph.** LoCoMo builds temporal event graphs with causal links during *generation*,
  but the release does not expose them - `event_summary` is free text per speaker per session,
  no ids, no edges (verified by parsing the actual `locomo10.json`, not from the README).
  LongMemEval is chat history plus `answer_session_ids` pointers, no event structure at all.
  **TCMF therefore cannot be run on either** without inducing a graph, which is out of scope and
  upstream of TCMF, and whose errors would dominate (W7). So this item measures the REGIME, not
  the method.
- **Result (n=273 real multi-hop questions, 10 conversations, `nomic-embed-text`):** ranking
  every unit of a conversation by similarity to the question and asking where the annotated gold
  evidence lands. At session granularity, assembling the full evidence set needs a median of
  **12 of 28 sessions (43% of the conversation)**, recall@5 = **0.505 [0.465, 0.545]**, and
  **77.7%** of questions have a needed session outside the top 5. The second piece of evidence
  is systematically harder to reach than the first. The regime is real outside the simulator.
- **I GOT THIS WRONG THE FIRST TIME AND THE WRONG NUMBER IS ON THE RECORD.** The first version
  ranked single dialogue turns and produced recall@5 = **0.066**, which I nearly reported as the
  headline. It is mostly an artifact of the retrieval unit: turns are one-line utterances, and
  no deployed system retrieves at that granularity. Re-running at session granularity moved it
  to 0.505, roughly 8x. The nomic `search_query`/`search_document` prefixes were the second
  confound and matter much less (0.066 -> 0.112 at turn level, nothing at session level). All
  four conditions are committed in `results_locomo/` so the turn rows stay visible as the reason
  the headline is what it is. **Report the session rows.**
- **Scope limit, written into the module docstring, the queue item, and the paper so it cannot
  drift:** this shows semantic similarity is INSUFFICIENT; it does NOT show causal-ancestor
  reachability is the remedy. LoCoMo's multi-hop links are plausibly entity/co-reference chains,
  not causal ones. The paper presents it as motivation for the regime, explicitly not as an
  evaluation of TCMF, and names inducing causal structure over a public corpus as the next
  paper rather than a missing experiment in this one.
- **Verified vs assumed:** verified - dataset structure by parsing it (5882 turns, 2815 evidence
  refs, only 9 unresolvable); the committed runner reproduces the exploratory script's numbers
  bit-for-bit through a completely different code path (sha1-keyed `EmbedClient` vs a raw-text
  cache), and a second run from cache reproduces them again; 10 new unit tests pass; full
  benchmark suite now 63 tests green. Assumed/not checked: only one encoder
  (`nomic-embed-text`) - N13's second-encoder item should cover this table too; and the
  category-1 "multi-hop" label is taken from LoCoMo's own annotation, not re-audited by hand.
- **Repo hygiene:** the LoCoMo dataset (2.7 MB, third-party) and the embedding cache (196 MB)
  are gitignored, not vendored; the runner documents the one-line fetch. `results_locomo.json`
  stores a stable per-conversation question INDEX rather than the verbatim question text, so a
  public repo does not redistribute third-party content while rows stay auditable.
- **Files touched (public repo):** `tcmfbench/locomo_regime.py`, `run_locomo_regime.py`,
  `test_locomo_regime.py`, `results_locomo/` (new), `.gitignore` (new), `NIGHT_QUEUE.md`,
  `NIGHT_LOG.md`. **(private repo):** `main.tex` (new subsection + `tab:locomo`),
  `references.bib` (LoCoMo entry, verified).
- **Next:** N05 for the routine. This item makes N16's scale work less urgent and makes N17
  (TCMFBench as a standalone artifact) more attractive, since the regime it tests is now shown
  to be one public benchmarks expose but do not isolate.
