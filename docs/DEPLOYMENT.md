# Deployment

CivilizationOS runs as two independent pieces on free tiers: the FastAPI backend on Render, and the static React frontend on Vercel. A GitHub Action keeps the backend warm.

| Piece | Where | Live URL |
|---|---|---|
| API and simulation | Render web service `civilizationos-api` (Docker, free plan) | https://civilizationos-api.onrender.com |
| Frontend (Vite build of `web/`) | Vercel, production branch `main` | https://civilization-os-murex.vercel.app |
| Keep-warm ping | GitHub Actions, `.github/workflows/keepalive.yml`, every 10 minutes | none |

## Public-demo mode

The cloud deploy sets `DEMO_MODE=true`. Ollama, the free local model tier, is not reachable from Render, so the always-on ambient loop (citizen small talk, reflection, emergent crises) is off. Crisis injection and council debates stay fully live and run on demand. Locally, with Ollama running, the full ambient simulation works at $0.

## First deploy

1. **Render:** dashboard, New, Blueprint, pick this repo. `render.yaml` and the `Dockerfile` at the repo root define the service.
2. **Set the dashboard-only values** (marked `sync: false` in `render.yaml` so they are never committed):

   | Variable | Value |
   |---|---|
   | `OPENROUTER_API_KEY` | your OpenRouter key |
   | `ADMIN_TOKEN` | a long random string; required on the public deploy, it gates `POST /speed` and the `/resolve` routes |
   | `OPENROUTER_FREE_MODEL` | `google/gemini-2.5-flash-lite`, serves the four debate roles |
   | `OPENROUTER_PREMIUM_MODEL` | `anthropic/claude-haiku-4.5`, serves the Synthesizer verdict |
   | `CORS_ORIGINS` | comma-separated origins allowed to call the API; add the Vercel URL, or the browser blocks every request |

   The OpenRouter account needs credit: both models are paid. Free `:free` models cap at 50 requests a day until $10 of credit is bought, which is why the debate slot uses a cheap paid model instead.
3. **Values already in `render.yaml`:** `DEMO_MODE`, `PREMIUM_MODE`, `CRISIS_COOLDOWN_S` (30 s), `CRISIS_DAILY_CAP` (60), `TIER2_BUDGET_USD` (15) and the four price fields. The price fields must match the two slugs above: USD per million tokens, from `openrouter.ai/api/v1/models`. If you change a slug, change its price pair in the same commit.
4. **Vercel:** import the repo with `web/` as the root. Set `VITE_API_BASE=https://civilizationos-api.onrender.com` and `VITE_WS_URL=wss://civilizationos-api.onrender.com/ws`. Leave both unset for local development, where Vite's dev proxy is used.
5. **Order matters:** deploy Render first, then Vercel, then add the Vercel URL to `CORS_ORIGINS` on Render.

## Verify a deploy

```
curl -sL https://civilizationos-api.onrender.com/health        # 200 after up to about 25 s on a cold start
curl -sIL https://civilization-os-murex.vercel.app | head -1   # 200, and the final URL is the app, not a login
```

Then open the frontend, inject a crisis, and watch a debate stream. In Render's logs, each LLM call emits one JSON line on the `civos.llm.calls` logger with tier, model, latency and cost, which is how to confirm the free and premium slots are actually serving.

## Free-tier behavior to expect

- Render sleeps the service after about 15 minutes idle and takes about 25 seconds to wake. The keep-warm Action pings `/health` every 10 minutes so the one warm slot stays occupied; Render's free plan gives 750 instance-hours a month per account, so only one service can be kept warm.
- No persistent disk and no database: the running society, causal graph and debates live in process memory and are lost on every restart or redeploy. This is deliberate for a demo.
- `TIER2_BUDGET_USD` resets on every process restart, so it is a per-process-lifetime ceiling, not a monthly one. `POST /crisis` is rate-limited by a global cooldown and a per-day cap for the same reason.

## Redeploy and roll back

Render redeploys on every push to `main` (the Blueprint default). To roll back, use the Render dashboard's deploy history and redeploy a previous build, or revert the commit. Vercel keeps every deployment, so promoting an earlier one restores the frontend.

## Secrets

Nothing secret is in the repo. `render.yaml` names each secret and leaves its value to the Render dashboard. The weekly fleet scan in `zaid-os` runs gitleaks over the default branch and pip-audit over `api/requirements.txt`.
