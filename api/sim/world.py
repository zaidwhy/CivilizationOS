"""The city: a small tile grid of named locations plus a world clock.

Deterministic and dependency-free so the simulation is reproducible from a seed
and fully unit-testable without any model. One in-world day is divided into phases
that drive each citizen's daily routine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

GRID_W = 24
GRID_H = 16
TICKS_PER_DAY = 240          # one tick ~= 6 in-world minutes
MINUTES_PER_TICK = (24 * 60) // TICKS_PER_DAY


class DayPhase(str, Enum):
    NIGHT = "night"       # 22:00-06:00  -> home (sleep)
    MORNING = "morning"   # 06:00-09:00  -> commons / commute
    WORK = "work"         # 09:00-17:00  -> workplace
    EVENING = "evening"   # 17:00-22:00  -> commons / social


class LocationType(str, Enum):
    HOME = "home"
    WORKPLACE = "workplace"
    COMMONS = "commons"      # park, market, cafe, plaza — social mixing
    INSTITUTION = "institution"  # seats of the Phase-2 councils


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    type: LocationType
    x: int
    y: int


# A hand-laid city. Homes cluster left, workplaces right, commons in the middle,
# institutions across the top — so commuting naturally mixes citizens in commons.
COMMONS: list[Location] = [
    Location("park", "Greenwood Park", LocationType.COMMONS, 11, 4),
    Location("market", "Central Market", LocationType.COMMONS, 12, 8),
    Location("cafe", "The Daily Grind", LocationType.COMMONS, 10, 11),
    Location("plaza", "Civic Plaza", LocationType.COMMONS, 13, 6),
]

WORKPLACES: list[Location] = [
    Location("clinic", "Mercy Clinic", LocationType.WORKPLACE, 20, 5),
    Location("press", "City Press", LocationType.WORKPLACE, 21, 9),
    Location("exchange", "Trade Exchange", LocationType.WORKPLACE, 22, 12),
    Location("precinct", "5th Precinct", LocationType.WORKPLACE, 19, 13),
    Location("hall", "City Hall Offices", LocationType.WORKPLACE, 20, 2),
]

INSTITUTIONS: list[Location] = [
    Location("inst_gov", "Government", LocationType.INSTITUTION, 4, 1),
    Location("inst_media", "Media", LocationType.INSTITUTION, 8, 1),
    Location("inst_police", "Police", LocationType.INSTITUTION, 12, 1),
    Location("inst_economy", "Economy", LocationType.INSTITUTION, 16, 1),
    Location("inst_health", "Healthcare", LocationType.INSTITUTION, 20, 1),
]


def phase_for_tick(tick: int) -> DayPhase:
    minutes = (tick % TICKS_PER_DAY) * MINUTES_PER_TICK
    hour = minutes // 60
    if 6 <= hour < 9:
        return DayPhase.MORNING
    if 9 <= hour < 17:
        return DayPhase.WORK
    if 17 <= hour < 22:
        return DayPhase.EVENING
    return DayPhase.NIGHT


def clock_label(tick: int) -> str:
    day = tick // TICKS_PER_DAY + 1
    minutes = (tick % TICKS_PER_DAY) * MINUTES_PER_TICK
    return f"Day {day} {minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class World:
    grid_w: int = GRID_W
    grid_h: int = GRID_H

    def __post_init__(self) -> None:
        self.locations: dict[str, Location] = {
            loc.id: loc for loc in COMMONS + WORKPLACES + INSTITUTIONS
        }

    def location(self, loc_id: str) -> Location:
        return self.locations[loc_id]

    def commons(self) -> list[Location]:
        return [l for l in self.locations.values() if l.type == LocationType.COMMONS]

    def snapshot(self) -> dict:
        return {
            "grid": {"w": self.grid_w, "h": self.grid_h},
            "locations": [
                {"id": l.id, "name": l.name, "type": l.type.value, "x": l.x, "y": l.y}
                for l in self.locations.values()
            ],
        }
