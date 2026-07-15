# Contributing

Thanks for looking at CivilizationOS. It is a personal portfolio project, but issues
and small, focused PRs are welcome.

## Ground rules

1. **Tests stay offline.** `api/tests/` never makes a live Ollama/Gemini/Claude call -
   `test_router.py` exercises tier-selection logic (which brain a request downgrades
   to under a given config) rather than real completions. A PR that adds a test
   requiring a live LLM or network call will be asked to restructure it as a pure-logic
   test instead.
2. **`PREMIUM_MODE=false` stays the default.** The app must run at $0/day on Ollama
   alone out of the box; Gemini and Claude tiers are opt-in.
3. **One concern per PR.** Small and surgical beats broad and clever.
4. **The 3-tier router is the only place that calls out to Ollama/Gemini/Claude.**
   `api/llm/router.py` owns provider selection and the spend cap; new providers or
   routing logic plug in there, nowhere else.
5. **Three.js EffectComposer chains must end with `OutputPass`** (r152+ requirement) -
   see `CityStage3D.tsx`. Dropping it renders the 3D city black.

## Dev setup

Follow the Quick Start in [README.md](README.md) (Python 3.12+, Node 18+), then:

```bash
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python -m pytest api/tests -q
```

All 61 tests should pass before and after your change. CI runs the same command on
every push and PR.

## Design context

`docs/tcmf.md` records the Temporal-Causal Memory Fusion scoring design, including
tradeoffs and what v2 would change. `MASTER_BUILD_LOG.md` has the phase-by-phase build
history. If your change alters a recorded design decision, update the relevant doc in
the same PR.
