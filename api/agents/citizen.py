"""A citizen agent: a body that moves through the city on a daily routine, plus a
mind (its MemoryStream). Movement and routine are deterministic and rule-based so
the simulation is cheap and reproducible; conversation text, importance rating, and
reflection are layered on by the engine (Tier-0/1 LLM, event-driven) to keep cost
near zero.
"""
from __future__ import annotations

from ..memory.stream import MemoryStream
from ..sim.world import DayPhase, World, phase_for_tick
from .personas import Persona


def _step_toward(a: int, b: int) -> int:
    return a + (1 if b > a else -1 if b < a else 0)


class Citizen:
    def __init__(self, persona: Persona) -> None:
        self.p = persona
        self.x = persona.home_x
        self.y = persona.home_y
        self.target_x = persona.home_x
        self.target_y = persona.home_y
        self.target_loc_id = f"home_{persona.id}"
        self.location_id = f"home_{persona.id}"   # where it currently *is*
        self.dest_name = "home"
        self.arrived_action = "resting at home"
        self.action = "sleeping"
        self.speech: str | None = None
        self.speech_ttl = 0
        self.talk_cooldown = 0
        self.memory = MemoryStream(persona.id)
        self.relationships: dict[str, float] = {}

    # ---- routine ----
    def decide_target(self, world: World, tick: int) -> None:
        """Pick where to head based on the time of day. Called each tick."""
        phase = phase_for_tick(tick)
        if phase == DayPhase.NIGHT:
            self._aim(self.p.home_x, self.p.home_y, f"home_{self.p.id}", "home", "resting at home")
        elif phase == DayPhase.WORK:
            loc = world.location(self.p.workplace_id)
            self._aim(loc.x, loc.y, loc.id, loc.name, f"working at {loc.name}")
        else:  # MORNING or EVENING -> socialize at favorite commons
            loc = world.location(self.p.favorite_commons)
            self._aim(loc.x, loc.y, loc.id, loc.name, f"spending time at {loc.name}")
        self._refresh_action()

    def _aim(self, x: int, y: int, loc_id: str, dest_name: str, arrived_action: str) -> None:
        self.target_x, self.target_y, self.target_loc_id = x, y, loc_id
        self.dest_name, self.arrived_action = dest_name, arrived_action

    def _refresh_action(self) -> None:
        self.action = self.arrived_action if self.arrived() else f"heading to {self.dest_name}"

    # ---- movement ----
    def step(self) -> None:
        if self.speech_ttl > 0:
            self.speech_ttl -= 1
            if self.speech_ttl == 0:
                self.speech = None
        if self.talk_cooldown > 0:
            self.talk_cooldown -= 1

        if self.arrived():
            self.location_id = self.target_loc_id
            self._refresh_action()
            return
        self.x = _step_toward(self.x, self.target_x)
        self.y = _step_toward(self.y, self.target_y)
        self.location_id = self.target_loc_id if self.arrived() else ""
        self._refresh_action()

    def arrived(self) -> bool:
        return self.x == self.target_x and self.y == self.target_y

    def at_shared_location(self) -> bool:
        """True when standing at a public location (not home, not commuting)."""
        return bool(self.location_id) and not self.location_id.startswith("home_")

    # ---- speech / relationships ----
    def say(self, text: str, ttl: int = 4) -> None:
        self.speech = text
        self.speech_ttl = ttl

    def adjust_relationship(self, other_id: str, delta: float) -> float:
        v = max(-1.0, min(1.0, self.relationships.get(other_id, 0.0) + delta))
        self.relationships[other_id] = v
        return v

    # ---- serialization ----
    def snapshot(self) -> dict:
        return {
            "id": self.p.id,
            "name": self.p.name,
            "occupation": self.p.occupation,
            "x": self.x,
            "y": self.y,
            "action": self.action,
            "location_id": self.location_id,
            "speech": self.speech,
        }
