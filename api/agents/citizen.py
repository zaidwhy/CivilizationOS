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

# Per-occupation crisis memory hooks — injected into citizen memory when a matching
# crisis template activates, giving each profession a distinct reaction to events.
OCCUPATION_CRISIS_OBSERVATIONS: dict[str, dict[str, str]] = {
    "doctor": {
        "pandemic":       "As a doctor I need to prepare triage protocols immediately — we'll be overwhelmed.",
        "drought":        "Dehydration cases are going to spike. I'm ordering IV fluids now.",
        "cyberattack":    "Our electronic patient records are down. Switching to paper charts.",
        "crime_wave":     "We're treating more assault victims at the clinic. The streets aren't safe.",
        "housing_crisis": "Patients are missing follow-up appointments — they say they can't afford the bus fare after rent.",
    },
    "nurse": {
        "pandemic":       "We don't have enough PPE for the whole ward. Someone has to go without.",
        "drought":        "Half the clinic staff look dehydrated themselves. This heat is merciless.",
        "cyberattack":    "I can't access medication records. Every order needs a double verbal check.",
        "crime_wave":     "Two patients tonight with injuries they say were from 'falls'. I don't believe them.",
        "housing_crisis": "Two colleagues gave notice this week. They can't afford to live anywhere near the clinic.",
    },
    "journalist": {
        "pandemic":       "The official case count doesn't match what doctors are telling me off the record.",
        "drought":        "City Hall is denying the reservoir is critical. I have the internal memos.",
        "cyberattack":    "Someone is trying very hard to control the narrative about this breach.",
        "election":       "I've had three sources contact me about voting irregularities in the same district.",
        "crime_wave":     "Police are under-reporting incidents by classifying them as 'civil disputes'.",
        "housing_crisis": "I have documents showing the developer got advance notice of the rezoning six weeks before it went public.",
    },
    "editor": {
        "pandemic":    "We're running the clinic numbers every day. The public deserves accurate data.",
        "cyberattack": "Our servers were probed last night. The attack on City Hall may be broader.",
        "election":    "Every claim about the results gets fact-checked before we print it. Every one.",
        "crime_wave":  "We will not run fear-mongering headlines. Facts, context, attribution.",
    },
    "trader": {
        "pandemic":    "Supply chains are already seizing up. I'm hedging commodity exposure now.",
        "drought":     "Food futures are spiking and the exchange algorithms are amplifying the panic.",
        "cyberattack": "Settlement systems are frozen. Every open position is a blind risk right now.",
        "election":    "Markets hate uncertainty. I'm moving to cash until this resolves.",
        "crime_wave":  "Theft is up 30% at the market district. My insurance won't cover it all.",
    },
    "analyst": {
        "pandemic":    "The R-value from the clinic data suggests exponential spread within 9 days.",
        "drought":     "The reservoir drawdown rate means we have 23 days of supply at current usage.",
        "cyberattack": "The breach pattern matches the state-sponsored toolkit from last year's advisory.",
        "election":    "The statistical anomaly in precinct 7 is 4.2 standard deviations from expected.",
        "crime_wave":  "Crime clustering has a 0.87 correlation with the three blocks around the park.",
    },
    "officer": {
        "pandemic":    "We're enforcing quarantine zones but half the force is already calling in sick.",
        "cyberattack": "Our dispatch system is down. We're coordinating on analog radios.",
        "election":    "Tensions outside the counting centre are escalating. We need more units.",
        "crime_wave":  "We've had a 40% surge in calls tonight. The precinct is stretched thin.",
    },
    "civil servant": {
        "pandemic":    "I'm coordinating emergency permits for pop-up medical facilities.",
        "drought":     "Water rationing ordinance needs mayoral sign-off. I'm drafting it tonight.",
        "cyberattack": "City systems are going to manual override. This will be a very long week.",
        "election":    "I'm not allowed to comment on the certification process. Ask the commission.",
    },
    "barista": {
        "pandemic":    "Half my regulars haven't come in. I keep the cafe open so people have somewhere to go.",
        "drought":     "Can't make espresso with rationed water. People are still coming in just to talk.",
        "cyberattack": "Card readers are all down. Cash only and no one carries cash anymore.",
        "election":    "The arguments in here are getting heated. I've had to ask two people to leave.",
        "crime_wave":  "I'm closing an hour early until things settle down. It's not worth the risk.",
    },
    "shopkeeper": {
        "pandemic":       "I'm limiting customers to five at a time. Some argue, but I hold the line.",
        "drought":        "Rationing supplies across the whole neighbourhood — family accounts first.",
        "cyberattack":    "My inventory system is down. Running on a paper ledger like my grandmother did.",
        "election":       "Half my customers are furious at the other half. I've banned politics at the counter.",
        "crime_wave":     "Two break-ins this week. I've started sleeping in the back with the door bolted.",
        "housing_crisis": "Three of my regular suppliers have left the district. Delivery costs have doubled.",
    },
}


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
        self.location_id = f"home_{persona.id}"
        self.dest_name = "home"
        self.arrived_action = "resting at home"
        self.action = "sleeping"
        self.speech: str | None = None
        self.speech_ttl = 0
        self.talk_cooldown = 0
        self.memory = MemoryStream(persona.id)
        self.relationships: dict[str, float] = {}
        # Phase 3 — crisis reaction state
        self.fear: float = 0.0
        self.active_crisis: str | None = None

    # ---- routine ----
    def decide_target(self, world: World, tick: int, closed_locations: set[str] | None = None) -> None:
        closed = closed_locations or set()
        phase = phase_for_tick(tick)
        if phase == DayPhase.NIGHT or self.fear > 0.7:
            self._aim(self.p.home_x, self.p.home_y, f"home_{self.p.id}", "home", "sheltering at home")
        elif phase == DayPhase.WORK and self.p.workplace_id not in closed:
            loc = world.location(self.p.workplace_id)
            self._aim(loc.x, loc.y, loc.id, loc.name, f"working at {loc.name}")
        elif phase == DayPhase.WORK and self.p.workplace_id in closed:
            self._aim(self.p.home_x, self.p.home_y, f"home_{self.p.id}", "home", "staying home (workplace closed)")
        else:
            commons_id = self.p.favorite_commons
            if commons_id in closed:
                commons_id = next(
                    (l.id for l in world.commons() if l.id not in closed),
                    None,
                )
            if commons_id:
                loc = world.location(commons_id)
                self._aim(loc.x, loc.y, loc.id, loc.name, f"spending time at {loc.name}")
            else:
                self._aim(self.p.home_x, self.p.home_y, f"home_{self.p.id}", "home", "staying home")
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
        return bool(self.location_id) and not self.location_id.startswith("home_")

    # ---- speech / relationships ----
    def say(self, text: str, ttl: int = 10) -> None:
        self.speech = text
        self.speech_ttl = ttl

    def adjust_relationship(self, other_id: str, delta: float) -> float:
        v = max(-1.0, min(1.0, self.relationships.get(other_id, 0.0) + delta))
        self.relationships[other_id] = v
        return v

    # ---- fear ----
    def apply_fear(self, amount: float) -> None:
        self.fear = min(1.0, self.fear + amount)

    def decay_fear(self, rate: float = 0.006) -> None:
        self.fear = max(0.0, self.fear - rate)

    def decay_relationships(self, rate: float = 0.0003) -> None:
        for oid in list(self.relationships):
            v = self.relationships[oid]
            if abs(v) < rate:
                del self.relationships[oid]
            else:
                self.relationships[oid] = v - rate if v > 0 else v + rate

    def occupation_crisis_observation(self, crisis_key: str) -> str | None:
        """Return an occupation-specific memory text for this crisis, or None."""
        return OCCUPATION_CRISIS_OBSERVATIONS.get(self.p.occupation, {}).get(crisis_key)

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
            "fear": round(self.fear, 2),
            "active_crisis": self.active_crisis,
        }
