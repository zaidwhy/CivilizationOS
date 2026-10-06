# Changelog

Newest first. There are no version tags beyond the `audit-2026-09-15` checkpoint, so entries are grouped by the dates and phases in `MASTER_BUILD_LOG.md`, which holds the full record.

## 2026-10-06

- Rebuilt the 3D city stage (`web/src/city/CityStage3D.tsx`). The old ground and walls used metalness with no environment map, so most of the scene rendered near black. Now: matte lit materials, a sky and lighting that follow the simulation clock (night windows glow, dawn and dusk warm), per-type building silhouettes (pitched homes, stepped council towers, tree-lined public spaces), and a camera that fits the whole 24 by 16 grid at any window size with a short fly-in.
- Citizens used to stand inside their building and were invisible. They now stand in a row in front of it, each with a distinct colour, a fear ring on the ground, a larger invisible hit volume for clicking, a walking bob and frame-rate independent movement.
- Added hover tooltips, a selection ring, a collapsible map key with a reset-view button, a loading state for the free host's cold start, and a cap of three ambient speech bubbles (hover or select shows any one). Fixed an empty black bubble that CSS2DRenderer was revealing over every citizen.
- A closed building now shows a red pulsing beam, not just a darker roof. Repeated crises of one kind collapse into one pill with a count.
- The speed slider disables itself with an explanation if the server answers 401 or 403, and crisis launches now say why they failed (rate limit, server asleep) instead of failing silently. Rewrote the onboarding copy and the empty inspector text to match the new map; corrected the tick tooltip (one tick is about 6 in-world minutes).

## 2026-09-16 to 2026-09-21

- Structured per-call LLM logging: one JSON line per call on the `civos.llm.calls` logger with call id, tier requested and used, model, latency, cost and tokens, on success and on failure.
- Rewrote `docs/tcmf.md`, which had described the original multiplicative fusion formula as current. It now tells the failure and the fix against `research/tcmf_paper/FINDINGS.md`: the original formula scored recall@5 0.02, and the shipped retriever scores 0.76 with the root cause at rank 1.
- Added `ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `SECURITY.md` and this changelog.
- Set real OpenRouter prices in `render.yaml` for the chosen slugs, `google/gemini-2.5-flash-lite` and `anthropic/claude-haiku-4.5`.
- Bumped pytest to 9.0.3 (fixes PYSEC-2026-1845) and pytest-asyncio to 1.4.0.
- The figure 3 committed-versus-generated test now compares floats at 1e-6 relative, after CI failed on last-digit differences between machines.
- CI installs the benchmark's figure dependency so the TCMF suite collects, and skips the sentence-transformers cache test where the encoder is absent.

## 2026-09-15

- Gated the shared-state write routes (`POST /speed`, both `/resolve` routes) behind an admin token, capped crisis injections per day, ran the 152-test TCMF benchmark in CI, and pinned the API requirements.
- Pointed badges and links at the `zaidwhy` organization, and set the test badge from real collected counts: 76 API tests and 152 benchmark tests.

## 2026-09-04 and 2026-09-05

- Added `LICENSE`, `CITATION.cff` and ORCID authorship metadata, and stopped tracking `CLAUDE.md`.
- Corrected finding F3 in the TCMF paper: the shipped multiplicative fusion scored 0.02, not 0.00.

## 2026-07-29 to 2026-08-11

- Public deploy: Render backend and Vercel frontend, with a unified OpenRouter option and demo mode (`DEMO_MODE`) for the cloud.
- TCMF paper work: retriever fixes after the benchmark, a decision-quality tier, and further ablations (candidate pool size, real embeddings, spurious edges, a second domain).

## 2026-07-21

- TCMF paper benchmark and the four retriever fixes: normalized-additive fusion in place of the multiplicative form, inverted depth weighting corrected, the crisis excluded as its own ancestor, and a large candidate pool.

## 2026-06 to 2026-07-02 - version 0.13.0

The build, closed out on 2026-07-02 at 61 API tests.

- **Phase 0:** foundation.
- **Phase 1, AGORA:** the living city, with citizens, routines, memory and conversations.
- **Phase 2, PANTHEON:** five-role council debates and the first TCMF retriever.
- **Phase 3:** crises and society dynamics.
- **Phase 4:** fine-tuning and MLOps.
- **Phase 5:** polish and demo readiness.
- **Phases 6 to 8:** verdict effects, a real relationship graph and stats panel, crisis resolution by id, verdict reopening, a force-directed graph, speech bubbles, and the fine-tuned model wired in.
- **Phases 9 and 10:** emergent crisis injection with a council track record, and a citizen faction system.
- **Phases 11 and 11b:** emotion history, alliance events, what-if verdicts, session export, crisis pulse, event toasts, a stability sparkline and a scenario launcher.
- **Phase 12:** the Three.js 3D city.
- **Phase 13:** story rewind, a chronicle redesign and UI polish.
- **Phase 14 (2026-07-02):** a refinement pass.
