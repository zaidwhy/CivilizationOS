"""Offline tests for the budget-capped OpenRouter client (no network, no key needed)."""
from __future__ import annotations

import json

import pytest

from .openrouter_client import BudgetExceeded, Ledger, OpenRouterClient


def _client(tmp_path, cap=0.01, cost=0.002):
    led = Ledger(tmp_path / "ledger.json", cap)
    c = OpenRouterClient("x/model", tmp_path / "cache.json", led, max_tokens=100)
    c._prices = (1e-7, 4e-7)
    calls = []

    def fake_post(body):
        calls.append(body)
        return {"choices": [{"message": {"content": "CAUSES: 1"}}],
                "usage": {"prompt_tokens": 500, "completion_tokens": 50, "cost": cost}}
    c._post = fake_post
    return c, led, calls


def test_records_reported_cost_and_caches(tmp_path):
    c, led, calls = _client(tmp_path)
    assert c.chat("hello") == "CAUSES: 1"
    assert c.chat("hello") == "CAUSES: 1"
    assert len(calls) == 1 and led.total == pytest.approx(0.002)
    c.flush()
    again = Ledger(tmp_path / "ledger.json", 0.01)
    assert again.total == pytest.approx(0.002) and again.data["calls"] == 1


def test_refuses_a_call_that_could_cross_the_cap(tmp_path):
    c, led, calls = _client(tmp_path, cap=0.0065, cost=0.002)
    c.chat("a")
    c.chat("b")
    with pytest.raises(BudgetExceeded):
        c.chat("c")
    assert len(calls) == 2 and led.total <= 0.0065


def test_key_never_reaches_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRET-TEST")
    c, led, _ = _client(tmp_path)
    c.chat("q")
    c.flush()
    for f in tmp_path.iterdir():
        assert "SECRET" not in f.read_text(encoding="utf-8")
