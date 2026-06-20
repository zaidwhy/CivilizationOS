"""Pre-defined crisis templates and world-state mutation logic (Phase 3 / Phase 5).

Each CrisisTemplate defines:
  - A human-readable name + description
  - Which institution councils it activates (primary + secondary)
  - How it mutates world state (location closure, citizen fear, resource scarcity)
  - Citizen reaction text injected into their memory stream on crisis injection

Phase 5 additions:
  - `resolution_text`: message broadcast when a crisis is manually resolved
  - `secondary_severity`: multiplier for secondary institution crises (default 0.7)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrisisTemplate:
    key: str
    name: str
    description: str
    primary_institution: str
    secondary_institutions: list[str] = field(default_factory=list)
    closed_locations: list[str] = field(default_factory=list)
    base_fear: float = 0.3
    workplace_fear_boost: dict[str, float] = field(default_factory=dict)
    duration_ticks: int = 480   # ~2 in-world days at 240 ticks/day
    citizen_observation: str = ""
    resolution_text: str = ""
    secondary_severity: float = 0.7
    verdict_fear_reduction: float = 0.12  # fear drop applied to all citizens when council verdict is reached


CRISIS_TEMPLATES: dict[str, CrisisTemplate] = {
    "pandemic": CrisisTemplate(
        key="pandemic",
        name="Pandemic Outbreak",
        description=(
            "A dangerous fever is spreading through the city. Hospitals are overwhelmed "
            "and the source has not been identified."
        ),
        primary_institution="inst_health",
        secondary_institutions=["inst_gov"],
        closed_locations=["clinic"],
        base_fear=0.5,
        workplace_fear_boost={"clinic": 0.3, "market": 0.1},
        duration_ticks=720,
        citizen_observation=(
            "A pandemic has broken out — people are falling ill across the city. "
            "The clinic is overwhelmed and officials are urging caution."
        ),
        resolution_text=(
            "The pandemic has been brought under control. Transmission rates are falling "
            "and the clinic is reopening to routine patients."
        ),
    ),
    "drought": CrisisTemplate(
        key="drought",
        name="Severe Drought",
        description=(
            "Water reserves are critically low. Food prices are spiking and the market "
            "is struggling to maintain supply."
        ),
        primary_institution="inst_economy",
        secondary_institutions=["inst_gov"],
        closed_locations=["market"],
        base_fear=0.3,
        workplace_fear_boost={"market": 0.2, "exchange": 0.2},
        duration_ticks=600,
        citizen_observation=(
            "A severe drought has struck — the market is rationing supplies and "
            "food prices have doubled in two days."
        ),
        resolution_text=(
            "Emergency water deliveries have stabilised the drought situation. "
            "The market is reopening and prices are beginning to fall."
        ),
    ),
    "cyberattack": CrisisTemplate(
        key="cyberattack",
        name="Cyberattack",
        description=(
            "City infrastructure systems have been breached. Administrative records, "
            "dispatch systems, and payment networks are offline."
        ),
        primary_institution="inst_gov",
        secondary_institutions=["inst_media", "inst_police"],
        closed_locations=["hall"],
        base_fear=0.35,
        workplace_fear_boost={"hall": 0.4, "press": 0.2, "precinct": 0.15},
        duration_ticks=360,
        citizen_observation=(
            "A cyberattack has disabled city systems — card readers, dispatch, and "
            "government portals are all offline. Confusion and rumours are spreading."
        ),
        resolution_text=(
            "City systems have been restored following the cyberattack. "
            "Investigators are tracing the origin of the breach."
        ),
    ),
    "election": CrisisTemplate(
        key="election",
        name="Contested Election",
        description=(
            "Election results are being disputed. Public trust in government is fracturing "
            "and tensions between supporters of each faction are rising."
        ),
        primary_institution="inst_gov",
        secondary_institutions=["inst_media"],
        closed_locations=[],
        base_fear=0.2,
        workplace_fear_boost={"hall": 0.15, "press": 0.2},
        duration_ticks=480,
        citizen_observation=(
            "The election results are being contested — the city is divided, "
            "arguments are breaking out in public spaces, and no one trusts the count."
        ),
        resolution_text=(
            "The election dispute has been resolved by an independent audit. "
            "The city is cautiously returning to normal."
        ),
    ),
    "crime_wave": CrisisTemplate(
        key="crime_wave",
        name="Crime Wave",
        description=(
            "A surge in crime has made citizens afraid to be out after dark. "
            "Break-ins, theft, and street assaults have tripled in the past week."
        ),
        primary_institution="inst_police",
        secondary_institutions=["inst_media"],
        closed_locations=["park"],
        base_fear=0.4,
        workplace_fear_boost={"precinct": 0.2, "market": 0.15},
        duration_ticks=360,
        citizen_observation=(
            "A crime wave is gripping the city — people are afraid to be out after dark "
            "and businesses are closing early."
        ),
        resolution_text=(
            "The crime wave has subsided following increased patrols. "
            "The park is safe to use again."
        ),
    ),
}
