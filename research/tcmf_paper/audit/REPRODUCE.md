# Reproducing the audit

Everything runs from this folder (`research/tcmf_paper/audit/`) with the repository's Python
3.12 environment. The only dependencies are `numpy` and `networkx` (already required by the
API) and `pytest` for the checks. Tier B also needs a local Ollama.

```bash
cd research/tcmf_paper/audit
PY=../../../.venv312/Scripts/python.exe        # or any Python 3.12 with numpy + networkx
export PYTHONIOENCODING=utf-8
```

## 1. Harness checks (seconds)

```bash
$PY -m pytest tests -q -p no:cacheprovider
```

Includes the parity tests: the ablation re-implementation must rank like the
production `TCMFRetriever` on six graph modes, differing only where two scores are exactly equal.

## 2. Tier A: retrieval, synthetic, fully offline (about 12 minutes)

```bash
$PY -m tcmfaudit.run_retrieval            # n=500 per cell; appends to results/retrieval/*.jsonl.gz
$PY -m tcmfaudit.analyze_retrieval        # writes results/retrieval/SUMMARY.md and tests.json
```

The runner is resumable: finished (cell, seed) pairs on disk are skipped, so a rerun against
the committed rows does nothing. To regenerate from zero, delete `results/retrieval/*.jsonl.gz`
first. Seeds are 0 to n-1 in every cell, so rows are paired across methods and across cells
that share a world configuration. `--only A5 P3` runs a subset; `--n 100` a smaller sample.

## 3. Cost (about 1 minute)

```bash
$PY -m tcmfaudit.run_cost                 # writes results/cost.json; wall clock, machine-specific
```

## 4. Tier B: LLM end task (needs Ollama)

Models: `qwen2.5:3b-instruct`, `llama3.2:3b`, `nomic-embed-text`, `all-minilm`
(`ollama pull <name>` for each).

```bash
$PY -m tcmfaudit.run_decision                                  # reader qwen, encoder nomic
$PY -m tcmfaudit.run_decision --reader llama3.2:3b             # second reader
$PY -m tcmfaudit.run_decision --encoder all-minilm             # second encoder
$PY -m tcmfaudit.analyze_decision                              # results/decision/SUMMARY.md
```

Every model call is cached with its verbatim output in `results/decision/cache_*.jsonl`, and
embeddings in `results/decision/emb_*.json`. With the committed caches present the three
commands above make no model calls and finish in seconds; that is the offline reproduction.
Deleting the caches reruns the models (about 25 minutes per reader on a 4 GB laptop GPU, most
of it the rolling summaries). Reader calls use temperature 0 and seed 0; a different Ollama
build or quantization can still change individual answers.

## The audited retriever and the current one

The audit examined `api/memory/tcmf.py` at commit `70a227d`. Its defaults were changed
afterwards. From current code:

- Every Tier A row regenerates exactly. `tcmf_deployed` passes the audited defaults to the
  production class (`retrievers.AUDITED`); `tcmf_current` uses whatever ships today and appears
  only in `F1_after_fix`.
- Tier B arms named `tcmf_shipped@...` regenerate exactly for the same reason. The three
  production-prompt arms of the audited version need that version's prompt code, so their
  numbers are frozen in `results/decision/SUMMARY_audited_70a227d.md`; to regenerate them,
  check out `70a227d` and the audit folder from commit `cbc7b3d`.
- `results/decision/SUMMARY.md` is what the commands in section 4 produce today.

## What is deterministic and what is not

| Part | Deterministic | Note |
|---|---|---|
| Tier A rows | yes, bit for bit | numpy seeded per scenario; no model, no network |
| Tier A intervals and p-values | yes | bootstrap and permutation seeds fixed in `stats.py` |
| Tier B from committed caches | yes | pure replay |
| Tier B from empty caches | no | depends on the Ollama build; temperature 0 narrows it |
| Cost | no | wall clock |
