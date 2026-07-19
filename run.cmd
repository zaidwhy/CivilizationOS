@echo off
REM One-click run parity (PROJECT-GENESIS.md Tier 6 item 43): starts the API and the
REM web dev server and opens the browser, mirroring this project's entry in
REM jarvis-launcher's jarvis.config.json ("run all" action) so the launcher and this
REM repo never drift. Double-click, or run from a terminal with no arguments.
setlocal

set "ROOT=%~dp0"

start "CivilizationOS API" /D "%ROOT%" cmd /k "set PYTHONIOENCODING=utf-8 && .venv\Scripts\uvicorn api.main:app --port 8000"
start "CivilizationOS Web" /D "%ROOT%web" cmd /k "npm run dev"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(30); while((Get-Date) -lt $deadline) { try { Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:5173' -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }; Start-Process 'http://localhost:5173'"

endlocal
