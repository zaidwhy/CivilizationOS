"""Pre-defined crisis templates and world-state mutation logic (Phase 3).

Each CrisisTemplate defines:
  - A human-readable name + description
  - Which institution councils it activates (primary + secondary)
  - How it mutates world state (location closure, citizen fear, resource scarcity)
  - Citizen reaction text injected into their memory stream

Crisis effects propagate each tick via Engine.apply_crisis_effects() until the
crisis is resolved (currently: after a configurable duration in ticks).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrisisTemplate:
    key: str
    name: str
    description: str
    # Institutions that should deliberate (primary first, secondary optional)
    primary_institution: str
    secondary_institutions: list[str] = field(default_factory=list)
    # Locations closed/impaired during this crisis (empty = none)
    closed_locations: list[str] = field(default_factory=list)
    # Base fear added to all citizens on injection (0-1)
    base_fear: float = 0.3
    # Fear added specifically to citizens at high-risk workplaces
    workplace_fear_boost: dict[str, float] = field(default_factory=dict)
    # Duration in ticks before auto-resolution
    duration_ticks: int = 480   # 2 in-world days
    # Observation text injected into every citizen's memory on injection
    citizen_observation: str = ""


CRISIS_TEMPLATES: dict[str, CrisisTemplate] = {
    "pandemic": CrisisTemplate(
        key="pandemic",
        name="Pandemic Outbreak",
        description="A dangerous fever is spreading through the city.",
        primary_institution="inst_health",
        secondary_institutions=["inst_gov"],
        closed_locations=["clinic"],
        base_fear=0.5,
        workplace_fear_boost={"clinic": 0.3},
        duration_ticks=720,
        citizen_observation="A pandemic has broken out — people are falling ill across the city.",
    ),
    "drought": CrisisTemplate(
        key="drought",
        name="Severe Drought",
        description="Water reserves are critically low. Food prices are spiking.",
        primary_institution="inst_economy",
        secondary_institutions=["inst_gov"],
        closed_locations=["market"],
        base_fear=0.3,
        workplace_fear_boost={"market": 0.2, "exchange": 0.2},
        duration_ticks=600,
        citizen_observation="A severe drought has struck — the market is struggling and food prices are surging.",
    ),
    "cyberattack": CrisisTemplate(
        key="cyberattack",
        name="Cyberattack",
        description="City infrastructure systems have been breached.",
        primary_institution="inst_gov",
        secondary_institutions=["inst_media", "inst_police"],
        closed_locations=["hall"],
        base_fear=0.35,
        workplace_fear_boost={"hall": 0.4, "press": 0.2},
        duration_ticks=360,
        citizen_observation="A cyberattack has disabled city systems — confusion and fear spread.",
    ),
    "election": CrisisTemplate(
        key="election",
        name="Contested Election",
        description="Election results are disputed; public trust in government is fracturing.",
        primary_institution="inst_gov",
        secondary_institutions=["inst_media"],
        closed_locations=[],
        base_fear=0.2,
        workplace_fear_boost={"hall": 0.1, "press": 0.15},
        duration_ticks=480,
        citizen_observation="The election results are being contested — the city is divided and tensions run high.",
    ),
    "crime_wave": CrisisTemplate(
        key="crime_wave",
        name="Crime Wave",
        description="A surge in crime has made citizens afraid to go out at night.",
        primary_institution="inst_police",
        secondary_institutions=["inst_media"],
        closed_locations=["park"],
        base_fear=0.4,
        workplace_fear_boost={"precinct": 0.2},
        duration_ticks=360,
        citizen_observation="A crime wave is gripping the city — people are afraid to be out after dark.",
    ),
}
