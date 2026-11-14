"""A deterministic lexical embedder for running without a model.

With ``use_llm=False`` (the hosted demo) there is no Ollama, so ``LLMRouter.embed`` has nothing
to call and nothing was embedded: every causal boost and every relevance score was 0 (audit
REPORT.md, "Found by reading the engine"). This embedder needs only numpy. It hashes content
words into a fixed number of signed buckets and L2-normalizes, so cosine similarity is word
overlap. It cannot see synonyms, which is the price of needing no model.

Its similarities live on a different scale from nomic-embed-text's, so it carries its own
causal threshold (``CAUSAL_SIM_THRESHOLD``) and its vectors must never share a store with a
model's vectors.
"""
from __future__ import annotations

import re
import zlib

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")

# Function words carry most of the overlap between two unrelated English sentences.
_STOPWORDS = frozenset(
    "a an and are as at be been but by for from has have he her his i in is it its me my "
    "no not of on or our she so that the their them they this to up was we were will with "
    "you your".split()
)

# Chosen on the engine's own texts. Each crisis description against its own template's citizen
# observation: 0.18 to 0.37 (median 0.31, 6 of 7 at or above 0.20). Against the other six
# templates' observations: at most 0.18. Occupation-specific observations share few words with
# the description (median 0.06) and mostly stay below it. A verdict memory, which quotes the
# verdict, scores about 0.7 against the verdict event. Seven templates is a small sample.
CAUSAL_SIM_THRESHOLD = 0.20


def _stem(word: str) -> str:
    """Crude plural folding so 'prices' meets 'price'. Deliberately nothing more."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


class HashingEmbedder:
    """Signed feature hashing of content words. Same text, same vector, in every process."""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def encode(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        # crc32, not hash(): str hashing is salted per process and would change every vector.
        for word in _TOKEN.findall(text.lower()):
            if word in _STOPWORDS:
                continue
            h = zlib.crc32(_stem(word).encode("utf-8"))
            vec[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        norm = float(np.linalg.norm(vec))
        return (vec / norm).tolist() if norm > 0 else vec.tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Same interface as ``LLMRouter.embed`` so the engine and retriever can take either."""
        return [self.encode(t) for t in texts]
