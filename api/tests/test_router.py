"""Tests for the 3-tier router's downgrade logic and spend guardrail.

These run with no network and no models — they exercise the routing decisions
and cost accounting that protect the budget.
"""
from __future__ import annotations

from api.config import Settings
from api.llm.router import LLMRouter, SpendTracker, Tier


def make_router(**overrides) -> LLMRouter:
    base = dict(
        premium_mode=False,
        tier2_budget_usd=15.0,
        gemini_api_key="",
        anthropic_api_key="",
    )
    base.update(overrides)
    return LLMRouter(settings=Settings(**base))


def test_local_request_stays_local():
    r = make_router()
    assert r.resolve_tier(Tier.LOCAL) == Tier.LOCAL


def test_free_downgrades_to_local_without_gemini_key():
    r = make_router(gemini_api_key="")
    assert r.resolve_tier(Tier.FREE) == Tier.LOCAL


def test_free_stays_free_with_gemini_key():
    r = make_router(gemini_api_key="g-key")
    assert r.resolve_tier(Tier.FREE) == Tier.FREE


def test_premium_downgrades_to_free_when_premium_mode_off():
    r = make_router(premium_mode=False, anthropic_api_key="a-key", gemini_api_key="g-key")
    assert r.resolve_tier(Tier.PREMIUM) == Tier.FREE


def test_premium_downgrades_all_the_way_to_local_when_nothing_available():
    r = make_router(premium_mode=False, anthropic_api_key="", gemini_api_key="")
    assert r.resolve_tier(Tier.PREMIUM) == Tier.LOCAL


def test_premium_served_when_fully_configured():
    r = make_router(premium_mode=True, anthropic_api_key="a-key")
    assert r.resolve_tier(Tier.PREMIUM) == Tier.PREMIUM


def test_premium_downgrades_when_budget_exhausted():
    r = make_router(premium_mode=True, anthropic_api_key="a-key", gemini_api_key="g-key")
    r.spend.spent_usd = 15.0  # at cap
    assert r.resolve_tier(Tier.PREMIUM) == Tier.FREE


def test_spend_tracker_accumulates_cost():
    t = SpendTracker(cap_usd=10.0)
    cost = t.record("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert round(cost, 2) == 6.00  # $1 in + $5 out per 1M
    assert t.tier2_calls == 1
    assert t.can_spend() is True


def test_spend_tracker_blocks_over_cap():
    t = SpendTracker(cap_usd=1.0)
    t.record("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)  # $3
    assert t.can_spend() is False
