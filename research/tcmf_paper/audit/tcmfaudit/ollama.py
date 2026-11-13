"""Local Ollama calls with an append-only JSONL cache, so a killed run resumes for free and
every raw model output stays on disk verbatim."""
from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np

HOST = "http://127.0.0.1:11434"
TIMEOUT_S = 300


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{HOST}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


class Generator:
    """Deterministic text generation (temperature 0, fixed seed) cached by model and prompt."""

    def __init__(self, model: str, cache_path: Path, max_tokens: int) -> None:
        self.model, self.cache_path, self.max_tokens = model, cache_path, max_tokens
        self.calls = 0
        self._cache: dict[str, dict] = {}
        # The committed cache is the gzipped archive; new calls append to the plain file.
        archive = cache_path.with_name(cache_path.name + ".gz")
        for path, opener in ((archive, gzip.open), (cache_path, open)):
            if path.exists():
                with opener(path, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        row = json.loads(line)
                        self._cache[row["key"]] = row
        cache_path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, prompt: str) -> dict:
        key = hashlib.sha1(f"{self.model}\x00{self.max_tokens}\x00{prompt}".encode("utf-8")).hexdigest()
        if key not in self._cache:
            out = _post("/api/generate", {
                "model": self.model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0, "seed": 0, "num_predict": self.max_tokens},
            })
            row = {
                "key": key, "model": self.model, "prompt": prompt, "response": out["response"],
                "prompt_tokens": out.get("prompt_eval_count", 0),
                "output_tokens": out.get("eval_count", 0),
                "seconds": out.get("total_duration", 0) / 1e9,
            }
            with self.cache_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._cache[key] = row
            self.calls += 1
        return self._cache[key]


def embed_all(texts: list[str], model: str, cache_path: Path) -> dict[str, np.ndarray]:
    """Unit-norm embeddings for every text, embedded raw (no task prefix), as the app does."""
    cache: dict[str, list[float]] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    missing = [t for t in dict.fromkeys(texts) if t not in cache]
    for start in range(0, len(missing), 32):
        batch = missing[start:start + 32]
        out = _post("/api/embed", {"model": model, "input": batch})
        cache.update(zip(batch, out["embeddings"]))
    if missing:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    result = {}
    for t in texts:
        v = np.asarray(cache[t], dtype=np.float64)
        result[t] = v / np.linalg.norm(v)
    return result
