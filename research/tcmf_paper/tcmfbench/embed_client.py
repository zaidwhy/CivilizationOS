"""Disk-cached embedding client for the real-text tier (Ollama nomic-embed-text).

Every unique text is embedded once and cached to JSON keyed by sha1(model + text), so reruns
are fast and reproducible and do not re-hit Ollama. Falls back with a clear error if the
server is unreachable and the text is not already cached.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


class EmbedClient:
    def __init__(self, model: str = "nomic-embed-text",
                 host: str = "http://localhost:11434",
                 cache_path: str | Path = "results_realtext/emb_cache.json",
                 timeout: float = 120.0) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.cache_path = Path(cache_path)
        self._cache: dict[str, list[float]] = {}
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))

    def _key(self, text: str) -> str:
        return hashlib.sha1(f"{self.model}\x00{text}".encode("utf-8")).hexdigest()

    def _embed_remote(self, text: str) -> list[float]:
        body = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/embeddings", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))["embedding"]

    def embed(self, text: str) -> list[float]:
        k = self._key(text)
        if k in self._cache:
            return self._cache[k]
        try:
            vec = self._embed_remote(text)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise RuntimeError(
                f"Ollama unreachable and text not cached ({self.host}, model={self.model}). "
                f"Start Ollama and `ollama pull {self.model}`. Original: {e}"
            ) from e
        self._cache[k] = vec
        return vec

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        out = [self.embed(t) for t in texts]
        self.flush()
        return out

    def flush(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._cache)
