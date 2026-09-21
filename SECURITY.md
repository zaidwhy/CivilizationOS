# Security policy

CivilizationOS is a solo research and portfolio project with a public demo deployment. This file says how to report a problem and what the design does and does not protect.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Email **sidzaid72@gmail.com** with what you found, how to reproduce it, and which deployed URL or commit it affects. This is a one-person project, so there is no formal response time, but a report gets read and answered.

GitHub's private vulnerability reporting is not enabled on this repository, so email is the channel.

## In scope

- The public API at `https://civilizationos-api.onrender.com` and the code in this repository.
- Anything that lets a visitor spend money, read a secret, change the simulation for other viewers, or run code on the server.

Out of scope: denial of service through volume alone against a free-tier host, and findings that need a compromised Render or Vercel account.

## What the design protects

- **Write endpoints need a token.** `POST /speed` and both `/resolve` routes require the `X-Admin-Token` header whenever `ADMIN_TOKEN` is configured, and the public deploy must configure it. Without one they are open, which is intended only for a local instance.
- **The one public write, `POST /crisis`, cannot burn the budget.** It is the point of the demo, so it stays public, but it is limited by a global cooldown (30 seconds) and a per-day cap (60), and paid model spend is capped by `TIER2_BUDGET_USD`.
- **CORS is an allow-list.** Origins come from settings and are never `*`.
- **No secrets in the repository.** `OPENROUTER_API_KEY`, `ADMIN_TOKEN` and the model slugs are set only in the Render dashboard. A weekly scan checks every public repo's default branch with gitleaks and audits `api/requirements.txt` with pip-audit.
- **No personal data.** The simulation holds only synthetic citizens; there are no accounts and nothing about a visitor is stored.

## Known limits

- **One shared admin secret,** not per-user credentials. Rotate it by changing `ADMIN_TOKEN` in the Render dashboard.
- **The rate limit is global, not per visitor,** so one person can use up the shared cooldown for everyone. That is the tradeoff for protecting the budget with no accounts.
- **State is in process memory.** A restart resets the society and the spend counter, so `TIER2_BUDGET_USD` is a per-process ceiling, not a monthly one.
- **Dependencies are pinned,** and advisories are checked weekly, but a pinned version can sit with a known advisory between checks.

## Supported versions

Only the current `main` branch is deployed and maintained.
