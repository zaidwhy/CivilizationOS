---
name: Bug report
about: Something in CivilizationOS doesn't work as expected
title: "[Bug] "
labels: bug
assignees: ''
---

**Describe the bug**
A clear description of what went wrong.

**To reproduce**
Steps to reproduce (backend/frontend action, crisis injected, council viewed):
```
.venv\Scripts\uvicorn api.main:app --reload --port 8000
# then...
```

**Expected behavior**
What you expected to happen instead.

**Environment**
- OS:
- Python version (`.venv\Scripts\python --version`, expect 3.12+):
- Node version (`node --version`):
- `PREMIUM_MODE` value and which LLM tiers were active (see `/health`):
- Ollama running, with `qwen2.5:3b-instruct` / `nomic-embed-text` pulled?

**Additional context**
Logs, stack traces, browser console errors, or anything else relevant. Redact any API
keys before pasting.
