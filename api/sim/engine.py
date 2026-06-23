"""The simulation engine — advances the world one tick at a time.

Each tick is cheap and deterministic: citizens choose a destination by time-of-day,
step one cell, and record observations when they arrive somewhere new. When two
compatible citizens share a public location the engine may spark a conversation;
the *text* of that conversation (and end-of-day reflections) is produced by the
Tier-0 local model in a background task, so the tick loop never blocks on the LLM
and the city keeps moving smoothly. With use_llm=False everything is rule-based and
fully reproducible from the seed — that's the mode the tests run in.

Phase 2: inject_crisis() adds a crisis node to the CausalGraph, activates the
relevant PANTHEON council, and streams DebateTurns into the CrisisRegistry.

Phase 5: tick_interval is mutable (speed control), resolve_crisis() removes active
template effects, and council verdicts are recorded as "decision" nodes in the
causal graph to close the crisis→debate→decision loop.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Callable, Awaitable

from ..agents.citizen import Citizen
from ..agents.council import COUNCILS, DebateTurn
from ..agents.personas import SEED_CITIZENS, Persona
from ..llm import Tier, get_router
from ..memory.causal_graph import CausalGraph
from ..memory.tcmf import TCMFRetriever
from ..sim.crisis import Crisis, CrisisRegistry
from ..sim.events import CRISIS_TEMPLATES, CrisisTemplate
from .world import TICKS_PER_DAY, World, clock_label, phase_for_tick

logger = logging.getLogger("civos.sim")

CONVO_COOLDOWN_TICKS = 12
IMPORTANCE = {"observation": 2.0, "conversation": 4.0, "reflection": 6.0, "event": 8.0, "decision": 9.0}

# Emergent auto-crisis thresholds
_AUTO_FEAR_THRESHOLD = 0.62      # avg fear that starts the countdown
_AUTO_SUSTAIN_TICKS = 180        # ticks of sustained fear before eruption (~3 min at 1 s/tick)
_AUTO_COMPOUND_THRESHOLD = 0.78  # at this severity a second crisis fires even if one is active
_AUTO_COOLDOWN_TICKS = 300       # min ticks between auto-generated crises


class Engine:
    def __init__(
        self,
        personas: list[Persona] | None = None,
        *,
        seed: int = 42,
        use_llm: bool = True,
    ) -> None:
        self.world = World()
        self.rng = random.Random(seed)
        self.use_llm = use_llm
        self.tick_count = 0
        self.tick_interval: float = 1.0  # wall-clock seconds per tick; mutable for speed control
        self.citizens: dict[str, Citizen] = {
            p.id: Citizen(p) for p in (personas or SEED_CITIZENS)
        }
        self._prev_location: dict[str, str] = {c.p.id: c.location_id for c in self.citizens.values()}
        self.event_log: list[dict] = []
        self._bg: set[asyncio.Task] = set()
        self._router = get_router() if use_llm else None
        # PANTHEON
        self.causal_graph = CausalGraph()
        self.tcmf = TCMFRetriever(self.causal_graph)
        self.crises = CrisisRegistry()
        self._on_debate_turn: Callable[[DebateTurn], Awaitable[None]] | None = None
        # Phase 3 — active crisis state
        self._active_templates: list[tuple[CrisisTemplate, int]] = []  # (template, expiry_tick)
        self._closed_locations: set[str] = set()
        self._verdict_reopened: set[str] = set()  # locations partially reopened by council verdict

    # ---- main step ----
    async def advance(self) -> dict:
        self.tick_count += 1
        tick = self.tick_count

        self._tick_crisis_effects(tick)

        for c in self.citizens.values():
            c.decay_fear()
            c.decay_relationships()
            c.decide_target(self.world, tick, closed_locations=self._closed_locations)
            c.step()
            self._record_arrival(c, tick)

        self._maybe_converse(tick)

        # Auto-escalation: simmering fear with no active crisis can spontaneously erupt
        if tick % 45 == 0 and self.use_llm and not self._active_templates:
            fears = [c.fear for c in self.citizens.values()]
            avg_fear = sum(fears) / len(fears) if fears else 0.0
            if avg_fear >= 0.60 and self.rng.random() < 0.14:
                self._spawn(self._auto_escalate(tick, avg_fear))

        if tick % TICKS_PER_DAY == 0:
            self._schedule_reflections(tick)

        return self.snapshot()

    async def _auto_escalate(self, tick: int, avg_fear: float) -> None:
        """Spontaneously inject a crisis when city-wide fear stays high with no active crisis."""
        candidates = ["crime_wave", "cyberattack", "housing_crisis", "pandemic"]
        key = self.rng.choice(candidates)
        tmpl = CRISIS_TEMPLATES[key]
        logger.info("Auto-escalation: %s triggered at avg_fear=%.2f tick=%d", key, avg_fear, tick)
        self._log_event(tick, "event", f"Tension erupts — {tmpl.name} breaks out spontaneously.")
        await self.inject_crisis(
            text=tmpl.description,
            institution_id=tmpl.primary_institution,
            severity=round(0.50 + avg_fear * 0.25, 2),
            template_key=key,
        )

    def _record_arrival(self, c: Citizen, tick: int) -> None:
        prev = self._prev_location.get(c.p.id, "")
        if c.location_id and c.location_id != prev and c.at_shared_location():
            loc = self.world.location(c.location_id)
            self._remember(c, f"Arrived at {loc.name}.", tick, "observation")
        self._prev_location[c.p.id] = c.location_id

    # ---- conversations ----
    def _maybe_converse(self, tick: int) -> None:
        groups: dict[str, list[Citizen]] = {}
        for c in self.citizens.values():
            if c.at_shared_location() and c.talk_cooldown == 0:
                groups.setdefault(c.location_id, []).append(c)

        for loc_id, members in groups.items():
            if len(members) < 2:
                continue
            members.sort(key=lambda c: c.p.id)
            a, b = self.rng.sample(members, 2)
            prob = 0.5 * (a.p.sociability + b.p.sociability) / 2 + 0.1
            if self.rng.random() > prob:
                continue
            self._start_conversation(a, b, loc_id, tick)

    def _start_conversation(self, a: Citizen, b: Citizen, loc_id: str, tick: int) -> None:
        a.talk_cooldown = b.talk_cooldown = CONVO_COOLDOWN_TICKS
        delta = 0.04 + 0.02 * a.p.sociability
        a.adjust_relationship(b.p.id, delta)
        b.adjust_relationship(a.p.id, delta)
        loc = self.world.location(loc_id)
        self._log_event(tick, "conversation", f"{a.p.name} and {b.p.name} talk at {loc.name}")

        if self.use_llm:
            self._spawn(self._llm_converse(a, b, loc.name, tick))
        else:
            line = f"{a.p.name}: Good to see you, {b.p.name.split()[0]}."
            a.say(line)
            self._remember(a, f"Talked with {b.p.name} at {loc.name}.", tick, "conversation")
            self._remember(b, f"Talked with {a.p.name} at {loc.name}.", tick, "conversation")

    async def _llm_converse(self, a: Citizen, b: Citizen, place: str, tick: int) -> None:
        crisis_note = ""
        if self._active_templates:
            tmpl = self._active_templates[0][0]
            crisis_note = f" The city is currently gripped by: {tmpl.name}."

        rel = a.relationships.get(b.p.id, 0.0)
        if rel > 0.5:
            rel_note = " You know them well and trust them."
        elif rel > 0.2:
            rel_note = " You've met before a few times."
        elif rel < -0.2:
            rel_note = " There is some tension between you."
        else:
            rel_note = ""

        prompt = (
            f"You are {a.p.name}, a {a.p.age}-year-old {a.p.occupation}. "
            f"Traits: {a.p.traits}. Background: {a.p.backstory}{crisis_note}"
            f" You run into {b.p.name} ({b.p.occupation}) at {place}.{rel_note}"
            f" Say ONE short, natural, in-character line of dialogue (max 18 words). "
            f"No quotes around your words. No stage directions."
        )
        try:
            res = await self._router.complete(prompt=prompt, tier=Tier.LOCAL, max_tokens=60, temperature=0.9)
            line = res.text.strip().split("\n")[0][:180]
        except Exception:
            logger.exception("conversation generation failed")
            line = f"Nice to see you, {b.p.name.split()[0]}."
        a.say(f"{a.p.name}: {line}")
        await self._remember_async(a, f"At {place}, I said to {b.p.name}: \"{line}\"", tick, "conversation")
        await self._remember_async(b, f"At {place}, {a.p.name} said to me: \"{line}\"", tick, "conversation")

    # ---- reflection ----
    def _schedule_reflections(self, tick: int) -> None:
        for c in self.citizens.values():
            if self.use_llm:
                self._spawn(self._llm_reflect(c, tick))

    async def _llm_reflect(self, c: Citizen, tick: int) -> None:
        recent = c.memory.important_since(since_tick=tick - TICKS_PER_DAY, k=8)
        if not recent:
            return
        bullets = "\n".join(f"- {m.text}" for m in recent)
        crisis_note = ""
        if self._active_templates:
            tmpl = self._active_templates[0][0]
            crisis_note = f" The city is gripped by a {tmpl.name}."
        fear_note = f" (I am currently at {c.fear:.0%} fear level.)" if c.fear > 0.2 else ""
        prompt = (
            f"You are {c.p.name}, a {c.p.age}-year-old {c.p.occupation}. "
            f"Traits: {c.p.traits}. Background: {c.p.backstory}{crisis_note}{fear_note}\n\n"
            f"Today's key moments:\n{bullets}\n\n"
            f"Write ONE honest, specific, in-character sentence about how you feel about "
            f"the city right now. Make it personal and revealing. No generic platitudes."
        )
        try:
            res = await self._router.complete(prompt=prompt, tier=Tier.LOCAL, max_tokens=90, temperature=0.85)
            await self._remember_async(c, f"Reflection: {res.text.strip()}", tick, "reflection")
        except Exception:
            logger.exception("reflection failed for %s", c.p.id)

    # ---- memory helpers ----
    def _remember(self, c: Citizen, text: str, tick: int, kind: str) -> None:
        c.memory.add(text, tick, kind=kind, importance=IMPORTANCE.get(kind, 3.0))

    async def _remember_async(self, c: Citizen, text: str, tick: int, kind: str) -> None:
        embedding = None
        if self.use_llm and self._router is not None:
            try:
                embedding = (await self._router.embed([text]))[0]
            except Exception:
                logger.exception("embedding failed")
        c.memory.add(text, tick, kind=kind, importance=IMPORTANCE.get(kind, 3.0), embedding=embedding)

    # ---- Phase 3: crisis effects per tick ----
    def _tick_crisis_effects(self, tick: int) -> None:
        self._active_templates = [
            (tmpl, exp) for tmpl, exp in self._active_templates if exp > tick
        ]
        self._closed_locations = set()
        for tmpl, _ in self._active_templates:
            self._closed_locations.update(tmpl.closed_locations)
        # Remove locations that were partially reopened by a council verdict
        self._closed_locations -= self._verdict_reopened

    def _apply_template_fear(self, tmpl: CrisisTemplate, tick: int) -> None:
        """Inject fear and occupation-specific memories into citizens."""
        for c in self.citizens.values():
            boost = tmpl.workplace_fear_boost.get(c.p.workplace_id, 0.0)
            c.apply_fear(tmpl.base_fear + boost)
            c.active_crisis = tmpl.key

            # Occupation-specific reaction takes priority over generic observation
            occ_obs = c.occupation_crisis_observation(tmpl.key)
            if occ_obs:
                self._remember(c, occ_obs, tick, "event")
            elif tmpl.citizen_observation:
                self._remember(c, tmpl.citizen_observation, tick, "event")

    # ---- Phase 2: crisis injection ----
    async def inject_crisis(
        self,
        text: str,
        institution_id: str,
        severity: float = 0.7,
        template_key: str | None = None,
    ) -> Crisis:
        tick = self.tick_count
        crisis = self.crises.create(text, tick, institution_id, severity, template_key=template_key)

        embedding: list[float] | None = None
        if self.use_llm and self._router:
            try:
                embedding = (await self._router.embed([text]))[0]
            except Exception:
                logger.exception("crisis embedding failed")

        self.causal_graph.add_event(
            crisis.causal_event_id,
            text=text,
            tick=tick,
            kind="crisis",
            institution_id=institution_id,
            embedding=embedding,
        )
        self.causal_graph.auto_link_predecessors(crisis.causal_event_id)
        self._log_event(tick, "crisis", f"CRISIS [{institution_id}]: {text}")
        logger.info("Crisis injected: %s -> %s", crisis.id, institution_id)

        tmpl = CRISIS_TEMPLATES.get(template_key or "")
        if tmpl:
            expiry = tick + tmpl.duration_ticks
            self._active_templates.append((tmpl, expiry))
            self._apply_template_fear(tmpl, tick)
            for sec_inst in tmpl.secondary_institutions:
                sec_council = COUNCILS.get(sec_inst)
                if sec_council:
                    sec_crisis = self.crises.create(text, tick, sec_inst, severity * tmpl.secondary_severity)
                    self.causal_graph.add_event(
                        sec_crisis.causal_event_id, text=text, tick=tick,
                        kind="crisis", institution_id=sec_inst, embedding=embedding,
                    )
                    self.causal_graph.link(crisis.causal_event_id, sec_crisis.causal_event_id)
                    self._spawn(self._run_debate(sec_crisis, sec_council, embedding))

        council = COUNCILS.get(institution_id)
        if council is None:
            logger.warning("No council for institution %s", institution_id)
            return crisis

        self._spawn(self._run_debate(crisis, council, embedding))
        return crisis

    async def _run_debate(self, crisis: Crisis, council, crisis_embedding) -> None:
        router = self._router or get_router()
        ctx = await self.tcmf.retrieve(
            question=crisis.text,
            citizens=self.citizens,
            tick=crisis.tick,
            institution_id=crisis.institution_id,
            crisis_event_id=crisis.causal_event_id,
            k=12,
            router=router if self.use_llm else None,
        )

        verdict_text: str | None = None
        first_turn = True
        async for turn in council.deliberate(ctx, router):
            if first_turn:
                self.crises.set_debate_id(crisis.id, turn.debate_id)
                first_turn = False
            self.crises.add_turn(turn.debate_id, turn)
            self._log_event(crisis.tick, "debate", f"[{turn.name}] {turn.text[:80]}…")
            if turn.is_final:
                verdict_text = turn.text
            if self._on_debate_turn:
                try:
                    await self._on_debate_turn(turn)
                except Exception:
                    logger.exception("debate broadcast failed")

        # Record the verdict as a "decision" node in the causal graph
        if verdict_text:
            debate_id = self.crises._crises[crisis.id].debate_id
            decision_id = f"dec_{crisis.id}"
            decision_emb: list[float] | None = None
            if self.use_llm and router:
                try:
                    decision_emb = (await router.embed([verdict_text]))[0]
                except Exception:
                    pass
            self.causal_graph.add_event(
                decision_id,
                text=verdict_text,
                tick=self.tick_count,
                kind="decision",
                institution_id=crisis.institution_id,
                embedding=decision_emb,
            )
            self.causal_graph.link(crisis.causal_event_id, decision_id)
            self._log_event(self.tick_count, "decision", f"VERDICT [{council.institution_id}]: {verdict_text[:80]}…")

            # Apply partial world-state effects: reduce fear, add decision memory to all citizens
            if crisis.template_key:
                tmpl = CRISIS_TEMPLATES.get(crisis.template_key)
                if tmpl:
                    self._apply_verdict_effects(tmpl, verdict_text)

        logger.info("Debate complete for crisis %s", crisis.id)

    # ---- Phase 5: crisis resolution ----
    def resolve_crisis(self, template_key: str) -> str | None:
        """Remove an active crisis template early. Returns resolution text or None if not active."""
        tmpl_obj = CRISIS_TEMPLATES.get(template_key)
        was_active = any(t.key == template_key for t, _ in self._active_templates)
        if not was_active:
            return None

        self._active_templates = [
            (t, exp) for t, exp in self._active_templates if t.key != template_key
        ]
        self._closed_locations = set()
        for t, _ in self._active_templates:
            self._closed_locations.update(t.closed_locations)
        self._closed_locations -= self._verdict_reopened

        # Clear verdict-reopened entries for the resolved template's locations
        if tmpl_obj:
            for loc in tmpl_obj.verdict_reopens:
                self._verdict_reopened.discard(loc)

        for c in self.citizens.values():
            if c.active_crisis == template_key:
                c.fear = max(0.0, c.fear - 0.3)
                c.active_crisis = None

        # Mark all registry crises with this template key as resolved
        for crisis in self.crises._crises.values():
            if crisis.template_key == template_key:
                crisis.resolved = True

        res_text = (
            tmpl_obj.resolution_text
            if tmpl_obj
            else "The crisis has been resolved."
        )
        self._log_event(self.tick_count, "event", f"RESOLVED: {res_text}")
        res_id = f"res_{template_key}_{self.tick_count}"
        self.causal_graph.add_event(
            res_id, text=res_text, tick=self.tick_count, kind="resolution",
        )
        return res_text

    def resolve_crisis_by_id(self, crisis_id: str) -> str | None:
        """Resolve any crisis by its registry ID — works for both template and custom crises."""
        crisis = self.crises.get_crisis(crisis_id)
        if crisis is None or crisis.resolved:
            return None

        self.crises.mark_resolved(crisis_id)

        if crisis.template_key:
            # Delegate to template resolution for full world-state effects
            result = self.resolve_crisis(crisis.template_key)
            if result:
                return result
            # Template already expired naturally — return resolution text anyway
            tmpl = CRISIS_TEMPLATES.get(crisis.template_key)
            return tmpl.resolution_text if tmpl else "The crisis has concluded."

        # Custom (free-text) crisis — generic resolution
        for c in self.citizens.values():
            c.fear = max(0.0, c.fear - 0.15)
        res_text = "The crisis has been brought under control through institutional action."
        self._log_event(self.tick_count, "event", f"RESOLVED (custom): {res_text}")
        res_id = f"res_{crisis_id}_{self.tick_count}"
        self.causal_graph.add_event(
            res_id, text=res_text, tick=self.tick_count, kind="resolution",
        )
        return res_text

    def _apply_verdict_effects(self, tmpl: CrisisTemplate, verdict_text: str) -> None:
        """Partial fear reduction + decision memory + partial location reopening on verdict."""
        summary = verdict_text[:100].rstrip()
        tick = self.tick_count
        for c in self.citizens.values():
            c.fear = max(0.0, c.fear - tmpl.verdict_fear_reduction)
            self._remember(
                c,
                f"Council issued directive on {tmpl.name}: {summary}",
                tick,
                "decision",
            )

        # Partially reopen locations designated safe by this verdict
        for loc in tmpl.verdict_reopens:
            self._verdict_reopened.add(loc)
            self._closed_locations.discard(loc)

        reopened_note = f" — {', '.join(tmpl.verdict_reopens)} partially reopened" if tmpl.verdict_reopens else ""
        self._log_event(tick, "decision", f"Council verdict applied — {tmpl.name} fear reduced{reopened_note}")

    # ---- events / snapshot ----
    def _log_event(self, tick: int, kind: str, text: str) -> None:
        self.event_log.append({"tick": tick, "kind": kind, "text": text})
        self.event_log = self.event_log[-50:]

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    def snapshot(self) -> dict:
        tick = self.tick_count
        minute_of_day = (tick % TICKS_PER_DAY) / TICKS_PER_DAY
        world_snap = self.world.snapshot()
        active_crises = [t.name for t, _ in self._active_templates]
        return {
            "type": "world",
            "tick": tick,
            "clock": clock_label(tick),
            "phase": phase_for_tick(tick).value,
            "day_progress": round(minute_of_day, 4),
            "grid": world_snap["grid"],
            "locations": world_snap["locations"],
            "citizens": [c.snapshot() for c in self.citizens.values()],
            "events": self.event_log[-8:],
            "active_crises": active_crises,
            "closed_locations": list(self._closed_locations),
        }

    def agent_detail(self, agent_id: str) -> dict | None:
        c = self.citizens.get(agent_id)
        if not c:
            return None
        return {
            "id": c.p.id,
            "name": c.p.name,
            "occupation": c.p.occupation,
            "traits": c.p.traits,
            "backstory": c.p.backstory,
            "action": c.action,
            "fear": round(c.fear, 2),
            "active_crisis": c.active_crisis,
            "memories": [
                {"tick": m.tick, "kind": m.kind, "text": m.text, "importance": m.importance}
                for m in c.memory.recent(15)
            ],
            "relationships": [
                {"id": oid, "name": self.citizens[oid].p.name, "affinity": round(v, 2)}
                for oid, v in sorted(c.relationships.items(), key=lambda kv: kv[1], reverse=True)
                if oid in self.citizens
            ],
        }

    def timeline(self, k: int = 60) -> list[dict]:
        """Return the most recent k causal graph events for the timeline panel."""
        events = self.causal_graph.recent_events(since_tick=0, k=k)
        return [
            {
                "id": e["id"],
                "text": e["text"],
                "tick": e["tick"],
                "kind": e["kind"],
                "institution_id": e.get("institution_id"),
            }
            for e in events
        ]
