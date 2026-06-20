"""Crisis injection and debate transcript registry.

A Crisis is an event the user injects into the simulation — it disrupts
citizen life and activates the relevant institutional council to deliberate.
The CrisisRegistry is the single source of truth for active crises and their
in-progress / completed debate transcripts.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from ..agents.council import DebateTurn

_crisis_ids = itertools.count(1)


@dataclass
class Crisis:
    id: str
    text: str
    tick: int
    severity: float          # 0-1
    institution_id: str
    debate_id: str           # populated once council is activated
    causal_event_id: str     # id of the node added to the CausalGraph
    template_key: str | None = None  # set when crisis originated from a template


class CrisisRegistry:
    def __init__(self) -> None:
        self._crises: dict[str, Crisis] = {}
        self._debates: dict[str, list[DebateTurn]] = {}

    def create(
        self,
        text: str,
        tick: int,
        institution_id: str,
        severity: float = 0.7,
    ) -> Crisis:
        cid = f"crisis_{next(_crisis_ids)}"
        crisis = Crisis(
            id=cid,
            text=text,
            tick=tick,
            severity=severity,
            institution_id=institution_id,
            debate_id="",
            causal_event_id=cid,
        )
        self._crises[cid] = crisis
        return crisis

    def set_debate_id(self, crisis_id: str, debate_id: str) -> None:
        if crisis_id in self._crises:
            self._crises[crisis_id].debate_id = debate_id

    def add_turn(self, debate_id: str, turn: DebateTurn) -> None:
        self._debates.setdefault(debate_id, []).append(turn)

    def get_debate(self, debate_id: str) -> list[DebateTurn]:
        return self._debates.get(debate_id, [])

    def list_crises(self) -> list[Crisis]:
        return sorted(self._crises.values(), key=lambda c: c.tick, reverse=True)

    def all_debates(self) -> dict[str, list[DebateTurn]]:
        return self._debates
