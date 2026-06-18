"""Tests for the episodic memory stream scoring (relevance x recency x importance)."""
from __future__ import annotations

from api.memory.stream import MemoryStream, RetrievalWeights


def test_importance_dominates_when_only_importance_weighted():
    s = MemoryStream("alice", RetrievalWeights(relevance=0, recency=0, importance=1, decay=0.02))
    s.add("trivial small talk", tick=0, importance=1)
    big = s.add("the city declared a state of emergency", tick=0, importance=10)
    top = s.retrieve(now=0, k=1)
    assert top[0].memory.id == big.id


def test_recency_prefers_newer_when_only_recency_weighted():
    s = MemoryStream("bob", RetrievalWeights(relevance=0, recency=1, importance=0, decay=0.1))
    old = s.add("old news", tick=0, importance=5)
    new = s.add("fresh news", tick=50, importance=5)
    top = s.retrieve(now=50, k=2)
    assert top[0].memory.id == new.id
    assert top[0].recency > top[1].recency
    assert old  # referenced


def test_relevance_uses_embeddings_when_present():
    s = MemoryStream("carol", RetrievalWeights(relevance=1, recency=0, importance=0))
    s.add("market prices rose", tick=0, importance=5, embedding=[1.0, 0.0])
    s.add("the river flooded", tick=0, importance=5, embedding=[0.0, 1.0])
    top = s.retrieve(now=0, query_embedding=[1.0, 0.05], k=2)
    assert "market" in top[0].memory.text


def test_retrieve_refreshes_last_access():
    s = MemoryStream("dave", RetrievalWeights(relevance=0, recency=1, importance=0, decay=0.05))
    m = s.add("something", tick=0, importance=5)
    s.retrieve(now=100, k=1)  # refresh -> last_access becomes 100
    assert m.last_access_tick == 100


def test_empty_stream_returns_empty():
    assert MemoryStream("eve").retrieve(now=10) == []


def test_negative_cosine_is_clamped_to_zero_relevance():
    s = MemoryStream("frank", RetrievalWeights(relevance=1, recency=0, importance=0))
    s.add("opposite", tick=0, importance=5, embedding=[1.0, 0.0])
    top = s.retrieve(now=0, query_embedding=[-1.0, 0.0], k=1)
    assert top[0].relevance == 0.0


def test_important_since_filters_by_tick():
    s = MemoryStream("grace")
    s.add("early", tick=0, importance=9)
    s.add("late minor", tick=10, importance=2)
    s.add("late major", tick=10, importance=8)
    res = s.important_since(since_tick=5, k=10)
    texts = [m.text for m in res]
    assert "early" not in texts
    assert res[0].text == "late major"
