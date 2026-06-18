"""Seed cast for the city — 10 citizens with homes, jobs, and dispositions.

Homes cluster on the west side of the grid; each citizen works at one workplace
and favours one commons for socializing. Traits/sociability shape behaviour and,
later, how they react to crises.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    age: int
    occupation: str
    traits: str
    workplace_id: str
    favorite_commons: str
    home_x: int
    home_y: int
    sociability: float  # 0-1, probability weight to start conversations


SEED_CITIZENS: list[Persona] = [
    Persona("ava", "Ava Reyes", 34, "doctor", "calm, principled, tired",
            "clinic", "cafe", 2, 3, 0.6),
    Persona("ben", "Ben Okafor", 41, "journalist", "curious, skeptical, blunt",
            "press", "plaza", 2, 5, 0.9),
    Persona("cleo", "Cleo Tanaka", 29, "trader", "ambitious, anxious, sharp",
            "exchange", "market", 2, 7, 0.7),
    Persona("dmitri", "Dmitri Volkov", 47, "officer", "loyal, wary, steady",
            "precinct", "park", 2, 9, 0.5),
    Persona("elena", "Elena Marsh", 38, "civil servant", "diplomatic, cautious",
            "hall", "plaza", 2, 11, 0.6),
    Persona("finn", "Finn Doyle", 23, "barista", "warm, chatty, dreamer",
            "cafe", "cafe", 3, 4, 0.95),
    Persona("greta", "Greta Lind", 52, "shopkeeper", "practical, frugal, kind",
            "market", "market", 3, 6, 0.7),
    Persona("hugo", "Hugo Mendes", 31, "nurse", "gentle, overworked, brave",
            "clinic", "park", 3, 8, 0.6),
    Persona("iris", "Iris Cohen", 27, "analyst", "logical, reserved, witty",
            "exchange", "cafe", 3, 10, 0.4),
    Persona("jonah", "Jonah Pike", 44, "editor", "cynical, eloquent, stubborn",
            "press", "plaza", 3, 12, 0.8),
]
