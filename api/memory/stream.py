"""Episodic memory stream (the AGORA half of the RAG).

Each agent owns a MemoryStream of timestamped observations. Retrieval scores every
memory by the generative-agents formula:

    score = w_rel * relevance + w_rec * recency + w_imp * importance

  * relevance  — cosine similarity of the query embedding to the memory embedding,
                 mapped to [0, 1] (0 when no embedding is available)
  * recency    — exponential decay over ticks since the memory was last accessed
                 (retrieving a memory refreshes it, so salient memories persist)
  * importance — an LLM- (or rule-) assigned 1-10 poignancy, normalized to [0, 1]

Phase 2's TCMF retriever fuses the output of these streams with the society-wide
causal graph. Embeddings are optional so the engine and tests can run without a
model; when absent, retrieval gracefully falls back to recency + importance.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from .vectorstore import VectorStore

_ids = itertools.count(1)


@dataclass
class Memory:
    id: str
    agent_id: str
    tick: int
    text: str
    kind: str = "observation"      # observation | conversation | reflection | event
    importance: float = 3.0        # 1-10
    last_access_tick: int = 0
    embedding: list[float] | None = None

    def __post_init__(self) -> None:
        self.last_access_tick = self.last_access_tick or self.tick


@dataclass
class RetrievalWeights:
    relevance: float = 1.0
    recency: float = 1.0
    importance: float = 1.0
    decay: float = 0.02  # per-tick exponential decay rate for recency


@dataclass
class ScoredMemory:
    memory: Memory
    score: float
    relevance: float
    recency: float
    importance: float


class MemoryStream:
    def __init__(self, agent_id: str, weights: RetrievalWeights | None = None) -> None:
        self.agent_id = agent_id
        self.weights = weights or RetrievalWeights()
        self.memories: dict[str, Memory] = {}
        self._vectors = VectorStore()

    def __len__(self) -> int:
        return len(self.memories)

    def add(
        self,
        text: str,
        tick: int,
        *,
        kind: str = "observation",
        importance: float = 3.0,
        embedding: list[float] | None = None,
    ) -> Memory:
        mem = Memory(
            id=f"{self.agent_id}:m{next(_ids)}",
            agent_id=self.agent_id,
            tick=tick,
            text=text,
            kind=kind,
            importance=float(importance),
            embedding=embedding,
        )
        self.memories[mem.id] = mem
        if embedding is not None:
            self._vectors.add(mem.id, embedding, {"kind": kind})
        return mem

    def _recency(self, mem: Memory, now: int) -> float:
        age = max(0, now - mem.last_access_tick)
        return math.exp(-self.weights.decay * age)

    def retrieve(
        self,
        now: int,
        *,
        query_embedding: list[float] | None = None,
        k: int = 5,
        refresh: bool = True,
    ) -> list[ScoredMemory]:
        """Top-k memories by the fused score. Retrieved memories are refreshed."""
        if not self.memories:
            return []

        sims = (
            self._vectors.similarities(query_embedding)
            if query_embedding is not None
            else {}
        )

        scored: list[ScoredMemory] = []
        w = self.weights
        for mem in self.memories.values():
            relevance = max(0.0, sims.get(mem.id, 0.0))  # clamp negative cosine to 0
            recency = self._recency(mem, now)
            importance = mem.importance / 10.0
            score = (
                w.relevance * relevance
                + w.recency * recency
                + w.importance * importance
            )
            scored.append(ScoredMemory(mem, score, relevance, recency, importance))

        scored.sort(key=lambda s: s.score, reverse=True)
        top = scored[:k]
        if refresh:
            for s in top:
                s.memory.last_access_tick = now
        return top

    def recent(self, k: int = 10) -> list[Memory]:
        return sorted(self.memories.values(), key=lambda m: m.tick, reverse=True)[:k]

    def important_since(self, since_tick: int, k: int = 10) -> list[Memory]:
        """Most important memories formed since a tick — feeds reflection."""
        pool = [m for m in self.memories.values() if m.tick >= since_tick]
        pool.sort(key=lambda m: m.importance, reverse=True)
        return pool[:k]
