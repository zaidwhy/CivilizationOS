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
