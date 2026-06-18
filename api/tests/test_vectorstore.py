"""Tests for the numpy-backed vector store (foundation of the TCMF RAG)."""
from __future__ import annotations

import numpy as np
import pytest

from api.memory.vectorstore import VectorStore, _normalize


def test_add_and_len():
    store = VectorStore()
    store.add("a", [1.0, 0.0, 0.0])
    store.add("b", [0.0, 1.0, 0.0])
    assert len(store) == 2


def test_cosine_ranking_is_correct():
    store = VectorStore()
    store.add("east", [1.0, 0.0])
    store.add("north", [0.0, 1.0])
    store.add("northeast", [1.0, 1.0])
    results = store.search([1.0, 0.1], k=3)
    # query points almost due-east -> 'east' best, 'north' worst
    assert results[0][0] == "east"
    assert results[-1][0] == "north"
    # similarities are bounded to [-1, 1]
    assert all(-1.0001 <= s <= 1.0001 for _, s in results)


def test_normalization_makes_magnitude_irrelevant():
    store = VectorStore()
    store.add("small", [3.0, 0.0])
    store.add("big", [0.0, 100.0])
    sims = store.similarities([0.0, 1.0])
    assert sims["big"] == pytest.approx(1.0, abs=1e-5)
    assert sims["small"] == pytest.approx(0.0, abs=1e-5)


def test_dim_mismatch_raises():
    store = VectorStore()
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError):
        store.add("b", [1.0, 0.0, 0.0])


def test_metadata_roundtrip():
    store = VectorStore()
    store.add("m1", [1.0, 0.0], {"kind": "event", "importance": 7})
    assert store.metadata("m1")["importance"] == 7
    assert store.metadata("missing") == {}


def test_empty_store_searches_safely():
    assert VectorStore().search([1.0, 0.0]) == []


def test_normalize_zero_vector_is_safe():
    out = _normalize(np.zeros(3))
    assert np.allclose(out, 0.0)
