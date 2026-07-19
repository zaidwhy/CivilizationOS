"""Tests for run.cmd (PROJECT-GENESIS.md Tier 6 item 43: one-click run parity).

Static-content checks only - run.cmd is a Windows batch script and this suite runs
on Linux CI, so it asserts the script's shape rather than executing it. Mirrors the
jarvis-launcher lesson (jarvis.py's `_write_script` docstring): a single level of
quoting per spawned console, never a quote nested inside another quoted string, or
cmd silently corrupts the command it runs.
"""
from __future__ import annotations

from pathlib import Path

RUN_CMD = Path(__file__).resolve().parents[2] / "run.cmd"


def _text() -> str:
    return RUN_CMD.read_text(encoding="utf-8")


def test_run_cmd_exists():
    assert RUN_CMD.is_file()


def test_starts_the_api_matching_jarvis_config():
    text = _text()
    assert "PYTHONIOENCODING=utf-8" in text
    assert ".venv\\Scripts\\uvicorn api.main:app --port 8000" in text


def test_starts_the_web_dev_server():
    assert "npm run dev" in _text()
    assert '/D "%ROOT%web"' in _text()


def test_opens_the_browser_on_the_web_port():
    assert "http://localhost:5173" in _text()


def test_no_nested_quoting_per_spawned_console():
    """Each `start ... cmd /k "..."` line must be made of cleanly balanced, non-nested
    quoted spans (title / working dir / command) - no quote character embedded inside
    another quoted span's content. This is the exact bug class jarvis-launcher's
    scratch-script rewrite fixed (see jarvis-launcher CLAUDE.md / jarvis.py): a quote
    nested inside a quoted string makes cmd execute the literal, corrupted text."""
    for line in _text().splitlines():
        if "cmd /k" not in line:
            continue
        assert '\\"' not in line, f"escaped quote (nesting) found in: {line!r}"
        assert '""' not in line, f"doubled quote (nesting) found in: {line!r}"
        opens = line.count('"')
        assert opens % 2 == 0, f"unbalanced quotes in: {line!r}"
        assert opens >= 4, f"expected at least a title + a command quoted span: {line!r}"
