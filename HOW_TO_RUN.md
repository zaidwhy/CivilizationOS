# CivilizationOS - How to Run & Test

**Version 0.13.0** | Last updated: 2026-07-02

---

## Prerequisites

- Python 3.12 with `.venv` set up (`pip install -r api/requirements.txt`) - Python 3.14 has a numpy ABI mismatch, use 3.12
- Node.js 18+ for the frontend
- [Ollama](https://ollama.com) running locally
- `qwen2.5:3b-instruct` pulled: `ollama pull qwen2.5:3b-instruct`
- `nomic-embed-text` pulled: `ollama pull nomic-embed-text`

---

## Start Everything

### 1. API (Terminal 1)
```powershell
cd C:\Users\Asus\projects\CivilizationOS
$env:PYTHONIOENCODING="utf-8"
& ".venv\Scripts\uvicorn" api.main:app --reload --port 8000
```

### 2. Frontend (Terminal 2)
```powershell
cd C:\Users\Asus\projects\CivilizationOS\web
npm run dev
```

### 3. Open Browser
```
http://localhost:5173
```

---

## Verify Setup

### API Health Check
```powershell
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
```

Expected output:
```json
{
  "status": "ok",
  "version": "0.13.0",
  "brains": {
    "local":   "qwen2.5:3b-instruct",
    "council": "civos-council",      ← purple pill in header
    "free":    null,
    "premium": null
  }
}
```

If `council` is `null`: check that `.env` contains `OLLAMA_COUNCIL_MODEL=civos-council` and that `ollama list` shows `civos-council`.

---

## Fine-Tuned Council Model (civos-council)

The project includes a locally fine-tuned Qwen2.5-3B model for council debates.

### Check it's registered
```powershell
ollama list | Select-String "civos"
# Expected: civos-council:latest   ...   1.9 GB
```

### If you need to recreate it
```powershell
# GGUF must be at ml/unsloth.Q4_K_M.gguf (1.84 GB, not in git)
# Download from Colab or ask for the file, then:
cd C:\Users\Asus\projects\CivilizationOS
ollama create civos-council -f ml/Modelfile
```

### Activate via .env
```
OLLAMA_COUNCIL_MODEL=civos-council
```
Restart the API after changing `.env`.

---

## Feature Test Checklist

### Simulation
- [ ] Citizens visible on the city grid, moving between locations
- [ ] Fear bars visible below citizen dots (should start at 0)
- [ ] Citizens speaking (speech bubbles appear with text, no "Name: " prefix)

### Council Chamber (PANTHEON)
- [ ] Crisis templates load (Pandemic, Drought, Cyberattack, Election, Crime Wave, Housing Crisis)
- [ ] Inject a crisis (e.g. "Pandemic") → debate starts streaming in
- [ ] 5 turns appear: Historian, Strategist, Skeptic, Predictor, then VERDICT (★)
- [ ] Debate complete indicator shows ✓
- [ ] Resolve button appears on active crisis badge → clicking it clears the crisis

### Fine-Tuned Model (if civos-council active)
- [ ] Purple 🧠 civos-council pill visible in header
- [ ] Inject a crisis and watch 4 debate turns - they come from local Ollama (fast, no API cost)
- [ ] `tier2_spent_usd` stays at 0.0 when `premium_mode: false`

### Relationship Graph
- [ ] Graph renders with citizen nodes and affinity edges
- [ ] Hover over a node → tooltip shows name, occupation, fear %, top 3 bonds
- [ ] Tooltip flips left when node is in right half of canvas

### Stats Panel
- [ ] Fear histogram updates as crises affect citizens
- [ ] Memory counts increase as citizens accumulate observations
- [ ] Debate count increments after each resolved debate

### Timeline
```powershell
Invoke-RestMethod "http://localhost:8000/timeline?k=10" | ConvertTo-Json
```

---

## Inject a Crisis via API

```powershell
$body = @{
  text = "A mystery illness is spreading through the clinic district"
  institution_id = "inst_health"
  severity = 0.8
} | ConvertTo-Json

Invoke-RestMethod "http://localhost:8000/crisis" -Method POST `
  -ContentType "application/json" -Body $body
```

---

## Run Tests

> Note: Tests require Python 3.12 (`.venv`). NumPy C extensions don't support Python 3.14 yet.

```powershell
.venv\Scripts\python -m pytest api/tests/ -q
# Expected: 61 passed
```

---

## .env Reference

```env
# Fine-tuned council model
OLLAMA_COUNCIL_MODEL=civos-council

# Optional: Tier 1 - Gemini free tier
GEMINI_API_KEY=your_key_here

# Optional: Tier 2 - Claude (requires PREMIUM_MODE=true)
ANTHROPIC_API_KEY=your_key_here
PREMIUM_MODE=false
```

All settings default to free/local if omitted. The app runs at $0/day on Ollama alone.

---

## Common Issues

| Problem | Fix |
|---|---|
| Purple pill not showing | Check `.env` has `OLLAMA_COUNCIL_MODEL=civos-council`, restart API |
| `civos-council` not found by Ollama | Run `ollama create civos-council -f ml/Modelfile` (needs GGUF at `ml/unsloth.Q4_K_M.gguf`) |
| Debate turns don't appear | WebSocket disconnected - refresh browser, check API is running |
| `uvicorn` command not found | Use `& ".venv\Scripts\uvicorn"` in PowerShell |
| Tests fail with numpy error | Use the Python 3.12 virtual env (`.venv`), not 3.14 |
