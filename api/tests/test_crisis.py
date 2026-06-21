"""Tests for Phase 3: crisis templates, fear propagation, location closure."""
from __future__ import annotations

import pytest

from api.sim.events import CRISIS_TEMPLATES
from api.sim.engine import Engine
from api.agents.personas import SEED_CITIZENS


class TestCrisisTemplates:
    def test_all_templates_have_required_fields(self):
        for key, tmpl in CRISIS_TEMPLATES.items():
            assert tmpl.key == key
            assert tmpl.name
            assert tmpl.primary_institution
            assert 0 <= tmpl.base_fear <= 1
            assert tmpl.duration_ticks > 0

    def test_pandemic_closes_clinic(self):
        tmpl = CRISIS_TEMPLATES["pandemic"]
        assert "clinic" in tmpl.closed_locations

    def test_secondary_institutions_are_valid(self):
        valid = {"inst_gov", "inst_media", "inst_police", "inst_economy", "inst_health"}
        for tmpl in CRISIS_TEMPLATES.values():
            assert tmpl.primary_institution in valid
            for sec in tmpl.secondary_institutions:
                assert sec in valid


class TestFearSystem:
    def _make_engine(self) -> Engine:
        return Engine(personas=SEED_CITIZENS[:3], seed=42, use_llm=False)

    def test_citizen_fear_starts_at_zero(self):
        eng = _make_engine = self._make_engine()
        for c in eng.citizens.values():
            assert c.fear == 0.0

    def test_apply_fear_clamps_to_one(self):
        eng = self._make_engine()
        c = next(iter(eng.citizens.values()))
        c.apply_fear(0.8)
        c.apply_fear(0.8)
        assert c.fear == 1.0

    def test_fear_decays_per_tick(self):
        eng = self._make_engine()
        c = next(iter(eng.citizens.values()))
        c.apply_fear(0.5)
        initial = c.fear
        c.decay_fear(rate=0.1)
        assert c.fear < initial

    def test_template_fear_applied(self):
        eng = self._make_engine()
        tmpl = CRISIS_TEMPLATES["pandemic"]
        eng._apply_template_fear(tmpl, tick=1)
        for c in eng.citizens.values():
            assert c.fear > 0

    @pytest.mark.asyncio
    async def test_advance_decays_fear(self):
        eng = self._make_engine()
        c = next(iter(eng.citizens.values()))
        c.apply_fear(0.5)
        before = c.fear
        await eng.advance()
        assert eng.citizens[c.p.id].fear < before


class TestResolveById:
    def _make_engine(self) -> Engine:
        return Engine(personas=SEED_CITIZENS[:3], seed=42, use_llm=False)

    @pytest.mark.asyncio
    async def test_resolve_template_crisis_by_id(self):
        eng = self._make_engine()
        crisis = await eng.inject_crisis("pandemic outbreak", "inst_health", template_key="pandemic")
        assert any(t.key == "pandemic" for t, _ in eng._active_templates)
        result = eng.resolve_crisis_by_id(crisis.id)
        assert result is not None
        assert not any(t.key == "pandemic" for t, _ in eng._active_templates)
        assert eng.crises.get_crisis(crisis.id).resolved

    @pytest.mark.asyncio
    async def test_resolve_custom_crisis_by_id(self):
        eng = self._make_engine()
        crisis = await eng.inject_crisis("strange fog covers the city", "inst_gov", template_key=None)
        result = eng.resolve_crisis_by_id(crisis.id)
        assert result is not None
        assert eng.crises.get_crisis(crisis.id).resolved

    def test_resolve_by_id_not_found_returns_none(self):
        eng = self._make_engine()
        assert eng.resolve_crisis_by_id("crisis_9999") is None

    def test_resolve_by_id_already_resolved_returns_none(self):
        eng = self._make_engine()
        eng.crises.mark_resolved("nonexistent")  # no-op
        c = eng.crises.create("test", 0, "inst_gov")
        eng.crises.mark_resolved(c.id)
        assert eng.resolve_crisis_by_id(c.id) is None

    def test_verdict_reopens_location(self):
        eng = self._make_engine()
        tmpl = CRISIS_TEMPLATES["pandemic"]
        eng._active_templates = [(tmpl, 9999)]
        eng._tick_crisis_effects(1)
        assert "clinic" in eng._closed_locations
        eng._apply_verdict_effects(tmpl, "The council mandates clinic reopening with safety protocols")
        assert "clinic" not in eng._closed_locations
        assert "clinic" in eng._verdict_reopened
        # Location stays open on subsequent ticks while crisis is still active
        eng._tick_crisis_effects(2)
        assert "clinic" not in eng._closed_locations

    def test_verdict_reopened_cleared_on_full_resolve(self):
        eng = self._make_engine()
        tmpl = CRISIS_TEMPLATES["pandemic"]
        eng._active_templates = [(tmpl, 9999)]
        eng._tick_crisis_effects(1)
        eng._apply_verdict_effects(tmpl, "Council directive issued")
        assert "clinic" in eng._verdict_reopened
        eng.resolve_crisis("pandemic")
        assert "clinic" not in eng._verdict_reopened


class TestLocationClosure:
    def test_closed_location_routes_citizen_home(self):
        from api.agents.citizen import Citizen
        from api.sim.world import World, DayPhase
        import api.sim.world as w_mod

        eng = Engine(personas=SEED_CITIZENS, seed=42, use_llm=False)
        # Advance to work phase (tick 38 = 09:00 in-world)
        # The clinic worker (ava) should go home if clinic is closed
        ava = eng.citizens["ava"]
        eng._closed_locations = {"clinic"}
        # Tick 38 is work phase
        ava.decide_target(eng.world, tick=38, closed_locations=eng._closed_locations)
        assert "home" in ava.dest_name

    @pytest.mark.asyncio
    async def test_crisis_expiry_reopens_locations(self):
        eng = Engine(personas=SEED_CITIZENS[:2], seed=42, use_llm=False)
        tmpl = CRISIS_TEMPLATES["pandemic"]
        eng._active_templates = [(tmpl, eng.tick_count + 2)]  # expires after 2 ticks
        eng._closed_locations = set(tmpl.closed_locations)

        await eng.advance()
        await eng.advance()
        # After expiry tick the closed set should be empty
        await eng.advance()
        assert "clinic" not in eng._closed_locations
