# Reproducing every table and figure

Every command below is offline and deterministic (fixed seeds), except the real-text and
decision tiers, which need a local Ollama. All commands run from `research/tcmf_paper/`.
Runtimes are wall-clock on the machine this was last regenerated on (Windows, CPU-only,
Ollama serving `qwen2.5:3b-instruct` + `nomic-embed-text` locally).

Every number cited in `FINDINGS.md` and the paper draft traces to one of the committed
`results_*/*.json` files below by exact command. If you find a number that does not, that is
a bug per the standing rule in `NIGHT_QUEUE.md` - find its source or delete the claim.

## Synthetic tier (fully offline, no Ollama)

| Result dir | Command | ~Runtime | Cache |
|---|---|---|---|
| `results_main` | `python -m tcmfbench.run_eval --n 300 --out results_main` | seconds | none needed (synthetic embeddings, computed not cached) |
| `results_mixed` | `python -m tcmfbench.run_mixed --n 300 --out results_mixed` | seconds | none |
| `results_main_pool80` | `python -m tcmfbench.run_eval --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_main_pool80` | ~5 min | none |
| `results_mixed_pool80` | `python -m tcmfbench.run_mixed --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_mixed_pool80` | ~3.5 min | none |
| `results_main_scale` | `python -m tcmfbench.run_eval --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_main_scale` | ~5 min | none |
| `results_mixed_scale` | `python -m tcmfbench.run_mixed --n 300 --seeds 0,1,2,3,4 --n-distractors 20 --n-noise 55 --out results_mixed_scale` | ~3.5 min | none |
| `results_main_tuned` | `python -m tcmfbench.run_tuned --regime pure --n 300 --out results_main_tuned` | ~1 min | none |
| `results_mixed_tuned` | `python -m tcmfbench.run_tuned --regime mixed --n 300 --out results_mixed_tuned` | ~1 min | none |
| `results_spurious` | `python -m tcmfbench.run_spurious --n 300 --grid-n 100 --out results_spurious` | a few min (roughly doubled by N11's added `dropout_curve` sweep, same protocol as the existing spurious-rate curve) | none |
| `results_theory` | `python -m tcmfbench.run_theory --out results_theory` | seconds | none |
| `results_lambda_sweep` | `python -m tcmfbench.run_lambda_sweep --n 300 --n-seeds 5 --out results_lambda_sweep` | ~2 min | none - the script itself asserts its own lambda=0.6/8 (mult) and lambda=4 (additive) points reproduce `results_main_scale/results.json` to machine precision before writing output |
| `figures/fig1_*` .. `figures/fig6_*` | `python figures/make_figures.py --out figures` (needs `pip install -r requirements-bench.txt`; Fig 4 needs `results_lambda_sweep/` to already exist, else it is skipped with a printed message; Fig 5 needs `results_mixed/` + `results_spurious/` to already exist; Fig 6 needs `results_decision/` to already exist - all three are committed) | seconds (figures only; excludes the result dirs they read) | `figures/fig1_scenario.json`, `figures/fig3_pairs.json`, `figures/fig6_data.json` (all committed; regenerated fresh each run, deterministic modulo the memory-id-string caveat noted in `tcmfbench/test_n10_n11_figures.py::_strip_volatile_ids` - every *numeric* field reproduces bit-for-bit even though `root_id`/`distractor_id` strings can shift between process invocations) |

**Checked, not a bug, but not bit-identical either:** running the documented command fresh
against the current codebase reproduces `results_main_scale`/`results_mixed_scale` exactly
(verified on `tcmf_add`, `graph_ppr`, `tcmf_shipped`, `causal_only`), but does **not** reproduce
`results_main_pool80`/`results_mixed_pool80` - e.g. mixed-regime `tcmf_add` recall@10 = 0.7983
(scale, and fresh) vs 0.7875 (pool80). This is a known, already-investigated discrepancy, not a
new finding: `results_*_pool80` came from an independently-written earlier harness (see
`FINDINGS.md`'s "Addendum - independent N01 replication" and `NIGHT_LOG.md`), deliberately left
unreconciled at the time as a noise estimate between two implementations of the same experiment,
pending N03's held-out tune split. N03 has since landed, and the paper's Table 8 (`sec:pool-scale`)
already cites the reproducible `scale` number (0.80), not the stale `pool80` number (0.79) - so
no claim in the paper is broken. The `_pool80` directories are superseded artifacts kept for
provenance (the addendum's own point is the ~0.01 cross-implementation noise estimate); `_scale`
is the one the paper actually draws from.

## Real-text tier (needs Ollama: `nomic-embed-text`)

| Result dir | Command | ~Runtime | Cache |
|---|---|---|---|
| `results_realtext` | `python -m tcmfbench.run_realtext --n 120 --out results_realtext` | first run: several min (encoder-bound); reruns: seconds | `results_realtext/emb_cache.json` (committed) |
| `results_n06` | `python -m tcmfbench.run_n06_domains --out results_n06` | first run: tens of min (200 scenarios to embed + ~1,200 local LLM calls for the decision tier); reruns: seconds | extends `results_realtext/emb_cache.json` and `results_decision/llm_cache.json` (both committed) |

## Decision-quality tier (needs Ollama: `qwen2.5:3b-instruct`)

| Result dir | Command | ~Runtime | Cache |
|---|---|---|---|
| `results_decision` | `python -m tcmfbench.run_decision --n 60 --out results_decision` | first run: a few min (60 x 10 = 600 LLM calls); reruns: seconds | `results_decision/llm_cache.json` (committed) |

**Found while building Fig 6 (N11), not fixed - out of scope for a figures-only item:** the
documented `results_decision` rerun command above no longer completes from only the committed
caches on a fresh CLOUD-OK checkout (no Ollama). `run_decision.py` calls
`realtext.generate_many_realtext` with no `domain_idx`, so it draws a random domain per
scenario from `realtext.DOMAINS` for the fixed base seed; `results_decision/results_decision.json`
was committed *before* N05 grew `DOMAINS` from 6 to 8 entries (the two new domains,
software-debugging and cybersecurity), so the same seed now draws a different domain sequence
than it did when the committed file was produced, and the resulting scenario texts are not in
`results_realtext/emb_cache.json`. This is the same category of issue as the already-documented
`_pool80` non-reproducibility above (a result committed before an upstream generator changed),
not a bug in the committed numbers themselves - they are frozen and correct for the codebase
state they were produced under. Fig 6 (`build_fig6_data` in `figures/make_figures.py`) does not
rerun `run_decision.py` at all - it reads the already-committed `results_decision.json` and
derives Wilson CIs from its `(mean, n)` alone, so this reproducibility gap does not block Fig 6.
Recorded rather than fixed here because fixing it is outside a figures-only item; whoever next
touches `run_decision.py` should either pin `domain_idx` to the original 6 governance domains
for reproducibility or accept and document a fresh, differently-seeded regeneration.

## LoCoMo public-benchmark check (N18, needs Ollama for embedding)

| Result dir | Command | Notes |
|---|---|---|
| `results_locomo` | `python -m tcmfbench.run_locomo_regime --data <path to locomo10.json>` | `locomo10.json` itself is not committed (third-party dataset, download separately) - `results_locomo/results_locomo.json` and the embedding cache are, so the finding is inspectable without re-downloading. |

**N10-N11 landed twice, reconciled 2026-08-11 (Night Shift collision - see NIGHT_QUEUE.md's N10/
N11 entries for the full account):** the kept figure set is Fig 3 + Fig 5 from a second,
independent build and Fig 4 + Fig 6 from the original. `results_main/results.json` gained a
`mult_lambda` ablation (same `mats`/pool/protocol as the existing `lambda` ablation, grid
`0.1, 0.3, 0.6, 1.2, 2.4, 8` - regenerated via the same `results_main` command above); not the
source of the kept Fig 4 (which reads `results_lambda_sweep/` instead) but left in place as an
independently-useful addition. `results_spurious/results_spurious.json` gained a `dropout_curve`
(same protocol as the existing spurious-rate `curve`, rates `0.0, 0.25, 0.5, 0.75, 1.0`,
regenerated via the same `results_spurious` command above) - not plotted either, but it is what
confirmed the realistic-pool F7 contradiction reproduces bit-for-bit against
`results_mixed_scale`'s own pre-existing `dropout_curve`. The kept Fig 5's dropout panel instead
reuses `results_mixed/results_mixed.json`'s pre-existing `dropout_curve` (Table `tab:dropout`'s
own small-pool, single-seed numbers) rather than either realistic-pool rerun - see the docstring
on `draw_fig5` in `figures/make_figures.py` for why.

## Not yet regenerable (open NIGHT_QUEUE.md items as of this writing)

N12 (ablation), N13 (second encoder + latency), N16 (scale/multi-crisis stress), N17
(TCMFBench spinoff) have no committed result artifact yet - their rows will be added to this
file the day each lands, not before. Do not cite a number for any of these; none exists.

## Structural validation (LaTeX draft, private repo)

From `paper/`: `.\build.ps1` runs `validate.py` (braces, environments, cross-references,
citations) then a full `pdflatex`/`bibtex`/`pdflatex`/`pdflatex` cycle, failing on any undefined
reference or citation (these otherwise compile silently as `??`). TinyTeX must be on PATH
(`%APPDATA%\TinyTeX\bin\windows`).
