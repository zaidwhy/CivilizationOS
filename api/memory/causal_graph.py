"""Society-wide temporal causal graph — one half of the TCMF retriever.

The causal graph tracks *what led to what* at the civilizational scale:
    crisis → council decision → policy outcome → downstream crisis

Nodes are events (observations, crises, decisions). Directed edges encode
causal precedence (A → B means A causally preceded / contributed to B) with
an optional strength weight. NetworkX DiGraph gives us free BFS/DFS for
causal-chain traversal.

TCMF retrieval uses this graph to answer: given the *current* crisis C,
which past events are its causal ancestors? Memories that are semantically
near those ancestors earn a depth-weighted boost over vanilla episodic RAG.
"""
from __future__ import annotations

import math
from typing import Iterator

import networkx as nx
import numpy as np


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


class CausalGraph:
    """Directed causal graph over civilizational events.

    Each node stores:
        text, tick, kind, institution_id, embedding (optional)
    Edges store:
        weight (0-1 causal strength, default 1.0)
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------ write

    def add_event(
        self,
        event_id: str,
        text: str,
        tick: int,
        kind: str = "event",
        *,
        institution_id: str | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        self._g.add_node(
            event_id,
            text=text,
            tick=tick,
            kind=kind,
            institution_id=institution_id,
            embedding=embedding,
        )

    def link(self, cause_id: str, effect_id: str, weight: float = 1.0) -> None:
        """Add a directed causal edge: cause → effect."""
        if cause_id in self._g and effect_id in self._g:
            self._g.add_edge(cause_id, effect_id, weight=weight)

    def auto_link_predecessors(
        self,
        new_event_id: str,
        window_ticks: int = 48,
        semantic_threshold: float = 0.5,
    ) -> None:
        """Link temporally nearby, semantically similar events as weak causes."""
        if new_event_id not in self._g:
            return
        new_data = self._g.nodes[new_event_id]
        new_tick = new_data["tick"]
        new_emb = new_data.get("embedding")

        for nid, data in self._g.nodes(data=True):
            if nid == new_event_id:
                continue
            age = new_tick - data["tick"]
            if age <= 0 or age > window_ticks:
                continue
            # temporal weight decays with age
            t_weight = math.exp(-0.05 * age)
            # semantic weight if both have embeddings
            s_weight = 0.0
            if new_emb and data.get("embedding"):
                sim = _cosine(new_emb, data["embedding"])
                s_weight = max(0.0, sim)
            combined = 0.5 * t_weight + 0.5 * s_weight
            if combined >= 0.3:
                self._g.add_edge(nid, new_event_id, weight=round(combined, 3))

    # ------------------------------------------------------------------ read

    def get_event(self, event_id: str) -> dict | None:
        if event_id not in self._g:
            return None
        return dict(self._g.nodes[event_id])

    def predecessors(self, event_id: str, max_depth: int = 4) -> dict[str, int]:
        """BFS backward from event_id; returns {ancestor_id: depth}."""
        if event_id not in self._g:
            return {}
        visited: dict[str, int] = {}
        queue: list[tuple[str, int]] = [(event_id, 0)]
        while queue:
            node, depth = queue.pop(0)
            for pred in self._g.predecessors(node):
                new_depth = depth + 1
                if pred not in visited and new_depth <= max_depth:
                    visited[pred] = new_depth
                    queue.append((pred, new_depth))
        return visited

    def semantic_search(
        self, query_embedding: list[float], k: int = 10
    ) -> list[tuple[str, float]]:
        """Top-k events by cosine similarity to a query embedding."""
        results: list[tuple[str, float]] = []
        for nid, data in self._g.nodes(data=True):
            emb = data.get("embedding")
            if emb is None:
                continue
            sim = _cosine(query_embedding, emb)
            results.append((nid, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def recent_events(self, since_tick: int, k: int = 20) -> list[dict]:
        """Events added after since_tick, newest first."""
        pool = [
            {"id": nid, **data}
            for nid, data in self._g.nodes(data=True)
            if data["tick"] >= since_tick
        ]
        pool.sort(key=lambda e: e["tick"], reverse=True)
        return pool[:k]

    def events_for_institution(self, institution_id: str) -> list[dict]:
        return [
            {"id": nid, **data}
            for nid, data in self._g.nodes(data=True)
            if data.get("institution_id") == institution_id
        ]

    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def node_ids(self) -> Iterator[str]:
        return iter(self._g.nodes)
