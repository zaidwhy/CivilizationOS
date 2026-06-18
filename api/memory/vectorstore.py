"""A tiny, dependency-free vector store backed by numpy.

At CivilizationOS's scale (~10 agents, a few hundred memories each) brute-force
cosine similarity over an in-memory matrix is fast and exact, with zero native
build dependencies. It also gives the TCMF retriever full control over scoring —
we expose raw similarity rather than hiding it behind a black-box index.

Vectors are L2-normalized on insert so similarity is a single matrix-vector dot.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class VectorRecord:
    id: str
    vector: np.ndarray          # normalized
    metadata: dict = field(default_factory=dict)


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


class VectorStore:
    """Append-only cosine-similarity store keyed by string id."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._matrix: np.ndarray | None = None   # shape (n, dim), rows normalized
        self._meta: dict[str, dict] = {}
        self._pos: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, id: str, vector, metadata: dict | None = None) -> None:
        vec = _normalize(vector).reshape(1, -1)
        if self._matrix is None:
            self._matrix = vec
        else:
            if vec.shape[1] != self._matrix.shape[1]:
                raise ValueError(
                    f"dim mismatch: got {vec.shape[1]}, store has {self._matrix.shape[1]}"
                )
            self._matrix = np.vstack([self._matrix, vec])
        self._pos[id] = len(self._ids)
        self._ids.append(id)
        self._meta[id] = metadata or {}

    def similarities(self, query) -> dict[str, float]:
        """Cosine similarity of `query` against every stored vector, by id."""
        if self._matrix is None:
            return {}
        q = _normalize(query)
        sims = self._matrix @ q  # rows are normalized -> dot == cosine
        return {self._ids[i]: float(sims[i]) for i in range(len(self._ids))}

    def search(self, query, k: int = 5) -> list[tuple[str, float]]:
        """Top-k (id, similarity) pairs, highest first."""
        sims = self.similarities(query)
        return sorted(sims.items(), key=lambda kv: kv[1], reverse=True)[:k]

    def metadata(self, id: str) -> dict:
        return self._meta.get(id, {})
