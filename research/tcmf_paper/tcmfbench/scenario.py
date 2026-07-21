"""Data model for a single benchmark scenario with known causal ground truth."""
from __future__ import annotations

from dataclasses import dataclass, field


# Memory labels drive ground truth.
#   gold_root / gold_chain : causal ancestors, semantically FAR from the crisis (found via the
#                            causal graph, missed by similarity)
#   gold_semantic          : genuinely relevant evidence semantically NEAR the crisis whose
#                            cause is unlogged (found via similarity, missed by the graph)
#   distractor             : semantically near-ish the crisis but causally irrelevant
#   noise                  : unrelated background
CAUSAL_GOLD_LABELS = ("gold_root", "gold_chain")
SEMANTIC_GOLD_LABELS = ("gold_semantic",)
GOLD_LABELS = CAUSAL_GOLD_LABELS + SEMANTIC_GOLD_LABELS


@dataclass
class EventSpec:
    id: str
    text: str
    tick: int
    topic: int
    embedding: list[float]
    institution_id: str
    kind: str = "event"


@dataclass
class MemorySpec:
    id: str            # assigned after insertion into a real MemoryStream
    citizen_id: str
    text: str
    tick: int
    topic: int
    importance: float
    embedding: list[float]
    label: str         # gold_root | gold_chain | distractor | noise


@dataclass
class Scenario:
    scenario_id: str
    institution_id: str
    # causal chain, root-cause first ... crisis last
    events: list[EventSpec]
    edges: list[tuple[str, str]]          # (cause_id, effect_id)
    crisis_event_id: str
    query_text: str
    query_embedding: list[float]
    memories: list[MemorySpec]
    # filled once memories are inserted into real streams (spec.id -> real Memory.id)
    gold_memory_ids: set[str] = field(default_factory=set)
    root_cause_memory_id: str | None = None

    def gold_specs(self) -> list[MemorySpec]:
        return [m for m in self.memories if m.label in GOLD_LABELS]
