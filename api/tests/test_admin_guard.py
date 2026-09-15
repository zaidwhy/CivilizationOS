"""Write endpoints on the public deploy: admin token on state changes, daily cap on spend."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api import main as api_main


@pytest.fixture
def admin_enabled(monkeypatch):
    monkeypatch.setattr(api_main.settings, "admin_token", "secret-token")
    yield
    # monkeypatch restores the attribute


def test_admin_guard_is_open_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(api_main.settings, "admin_token", "")
    api_main.require_admin(None)  # must not raise


def test_admin_guard_rejects_missing_or_wrong_header(admin_enabled):
    with pytest.raises(HTTPException) as exc:
        api_main.require_admin(None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        api_main.require_admin("wrong")


def test_admin_guard_accepts_the_configured_token(admin_enabled):
    api_main.require_admin("secret-token")


def test_speed_and_resolve_routes_carry_the_guard():
    guarded = {"/speed", "/crisis/{template_key}/resolve", "/crisis/id/{crisis_id}/resolve"}
    seen = set()
    for route in api_main.app.routes:
        if getattr(route, "path", None) in guarded and "POST" in getattr(route, "methods", set()):
            deps = [d.call for d in route.dependant.dependencies]
            assert api_main.require_admin in deps, route.path
            seen.add(route.path)
    assert seen == guarded


def test_daily_cap_blocks_after_n_injections(monkeypatch):
    monkeypatch.setattr(api_main.settings, "crisis_cooldown_s", 0.0)
    monkeypatch.setattr(api_main.settings, "crisis_daily_cap", 2)
    monkeypatch.setattr(api_main, "_last_crisis_injected_at", 0.0)
    monkeypatch.setattr(api_main, "_crisis_day", "")
    monkeypatch.setattr(api_main, "_crisis_count_today", 0)
    now = 1_800_000_000.0
    api_main._check_crisis_budget(now)
    api_main._crisis_count_today += 1
    api_main._check_crisis_budget(now + 1)
    api_main._crisis_count_today += 1
    with pytest.raises(HTTPException) as exc:
        api_main._check_crisis_budget(now + 2)
    assert exc.value.status_code == 429
    assert "Daily crisis cap" in exc.value.detail
    # a new UTC day resets the counter
    api_main._check_crisis_budget(now + 86_400)


def test_cooldown_still_applies(monkeypatch):
    monkeypatch.setattr(api_main.settings, "crisis_cooldown_s", 30.0)
    monkeypatch.setattr(api_main, "_last_crisis_injected_at", 1_800_000_000.0)
    with pytest.raises(HTTPException) as exc:
        api_main._check_crisis_budget(1_800_000_010.0)
    assert "rate-limited" in exc.value.detail
