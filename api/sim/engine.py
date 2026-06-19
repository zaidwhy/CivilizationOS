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
from .world import TICKS_PER_DAY, World, clock_label, phase_for_tick

logger = logging.getLogger("civos.sim")

CONVO_COOLDOWN_TICKS = 12      # a citizen won't re-initiate chatter for ~1 in-world hr
IMPORTANCE = {"observation": 2.0, "conversation": 4.0, "reflection": 6.0, "event": 8.0}


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
        self.citizens: dict[str, Citizen] = {
            p.id: Citizen(p) for p in (personas or SEED_CITIZENS)
        }
        self._prev_location: dict[str, str] = {c.p.id: c.location_id for c in self.citizens.values()}
        self.event_log: list[dict] = []
        self._bg: set[asyncio.Task] = set()
        self._router = get_router() if use_llm else None
        # Phase 2 — PANTHEON
        self.causal_graph = CausalGraph()
        self.tcmf = TCMFRetriever(self.causal_graph)
        self.crises = CrisisRegistry()
        # callback: (turn: DebateTurn) -> Awaitable[None] — set by main.py to broadcast
        self._on_debate_turn: Callable[[DebateTurn], Awaitable[None]] | None = None

    # ---- main step ----
    async def advance(self) -> dict:
        self.tick_count += 1
        tick = self.tick_count

        for c in self.citizens.values():
            c.decide_target(self.world, tick)
            c.step()
            self._record_arrival(c, tick)

        self._maybe_converse(tick)

        if tick % TICKS_PER_DAY == 0:
            self._schedule_reflections(tick)

        return self.snapshot()

    def _record_arrival(self, c: Citizen, tick: int) -> None:
        prev = self._prev_location.get(c.p.id, "")
        if c.location_id and c.location_id != prev and c.at_shared_location():
            loc = self.world.location(c.location_id)
            self._remember(c, f"Arrived at {loc.name}.", tick, "observation")
        self._prev_location[c.p.id] = c.location_id

    # ---- conversations ----
    def _maybe_converse(self, tick: int) -> None:
        # group co-located citizens at public places
        groups: dict[str, list[Citizen]] = {}
        for c in self.citizens.values():
            if c.at_shared_location() and c.talk_cooldown == 0:
                groups.setdefault(c.location_id, []).append(c)

        for loc_id, members in groups.items():
            if len(members) < 2:
                continue
            members.sort(key=lambda c: c.p.id)  # determinism
            a, b = self.rng.sample(members, 2)
            prob = 0.5 * (a.p.sociability + b.p.sociability) / 2 + 0.1
            if self.rng.random() > prob:
                continue
            self._start_conversation(a, b, loc_id, tick)

    def _start_conversation(self, a: Citizen, b: Citizen, loc_id: str, tick: int) -> None:
        a.talk_cooldown = b.talk_cooldown = CONVO_COOLDOWN_TICKS
        delta = 0.05
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
        prompt = (
            f"You are {a.p.name}, a {a.p.age}-year-old {a.p.occupation} "
            f"({a.p.traits}). You run into {b.p.name} ({b.p.occupation}) at {place}. "
            f"Say ONE short, natural line of dialogue (max 18 words). No quotes."
        )
        try:
            res = await self._router.complete(prompt=prompt, tier=Tier.LOCAL, max_tokens=48, temperature=0.9)
            line = res.text.strip().split("\n")[0][:160]
        except Exception:
            logger.exception("conversation generation failed")
            line = f"Nice to see you, {b.p.name.split()[0]}."
        a.say(f"{a.p.name}: {line}")
        await self._remember_async(a, f"At {place}, I told {b.p.name}: {line}", tick, "conversation")
        await self._remember_async(b, f"At {place}, {a.p.name} said: {line}", tick, "conversation")

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
        prompt = (
            f"You are {c.p.name} ({c.p.traits}). Reflecting on today:\n{bullets}\n\n"
            f"Write ONE sentence capturing how you feel about the city right now."
        )
        try:
            res = await self._router.complete(prompt=prompt, tier=Tier.LOCAL, max_tokens=60, temperature=0.8)
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

    # ---- Phase 2: crisis injection ----
    async def inject_crisis(
        self,
        text: str,
        institution_id: str,
        severity: float = 0.7,
    ) -> Crisis:
        """Inject a crisis, activate the PANTHEON council, stream debate turns."""
        tick = self.tick_count
        crisis = self.crises.create(text, tick, institution_id, severity)

        # Add crisis to causal graph
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

        council = COUNCILS.get(institution_id)
        if council is None:
            logger.warning("No council for institution %s", institution_id)
            return crisis

        # Debate runs as a background task so the HTTP response returns immediately
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

        first_turn = True
        async for turn in council.deliberate(ctx, router):
            if first_turn:
                self.crises.set_debate_id(crisis.id, turn.debate_id)
                first_turn = False
            self.crises.add_turn(turn.debate_id, turn)
            self._log_event(crisis.tick, "debate", f"[{turn.name}] {turn.text[:80]}…")
            if self._on_debate_turn:
                try:
                    await self._on_debate_turn(turn)
                except Exception:
                    logger.exception("debate broadcast failed")

        logger.info("Debate complete for crisis %s", crisis.id)

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
        return {
            "type": "world",
            "tick": tick,
            "clock": clock_label(tick),
            "phase": phase_for_tick(tick).value,
            "day_progress": round(minute_of_day, 4),
            "grid": self.world.snapshot()["grid"],
            "locations": self.world.snapshot()["locations"],
            "citizens": [c.snapshot() for c in self.citizens.values()],
            "events": self.event_log[-8:],
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
            "action": c.action,
            "memories": [
                {"tick": m.tick, "kind": m.kind, "text": m.text, "importance": m.importance}
                for m in c.memory.recent(12)
            ],
            "relationships": [
                {"id": oid, "name": self.citizens[oid].p.name, "affinity": round(v, 2)}
                for oid, v in sorted(c.relationships.items(), key=lambda kv: kv[1], reverse=True)
                if oid in self.citizens
            ],
        }
