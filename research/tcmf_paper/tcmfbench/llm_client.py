"""Disk-cached chat client for the decision-quality experiment (Ollama chat models).

Every unique (model, prompt) pair is answered once and cached to JSON keyed by
sha1(model + prompt), so reruns with temperature 0 / seed 0 are exact and do not re-hit
Ollama. Falls back with a clear error if the server is unreachable and the prompt is not
already cached.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


class LLMClient:
    def __init__(self, model: str = "qwen2.5:3b-instruct",
                 host: str = "http://localhost:11434",
                 cache_path: str | Path = "results_decision/llm_cache.json",
                 timeout: float = 120.0) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.cache_path = Path(cache_path)
        self._cache: dict[str, str] = {}
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))

    def _key(self, prompt: str) -> str:
        return hashlib.sha1(f"{self.model}\x00{prompt}".encode("utf-8")).hexdigest()

    def _chat_remote(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "seed": 0},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        return resp["message"]["content"]

    def chat(self, prompt: str) -> str:
        k = self._key(prompt)
        if k in self._cache:
            return self._cache[k]
        try:
            text = self._chat_remote(prompt)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise RuntimeError(
                f"Ollama unreachable and prompt not cached ({self.host}, model={self.model}). "
                f"Start Ollama and `ollama pull {self.model}`. Original: {e}"
            ) from e
        self._cache[k] = text
        return text

    def flush(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._cache)
