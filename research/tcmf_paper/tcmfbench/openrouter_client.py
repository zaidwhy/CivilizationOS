"""Budget-capped, disk-cached chat client for OpenRouter (paid models), same interface as
``LLMClient`` (``chat`` / ``flush``), so any experiment can swap it in.

Money rules, enforced in code rather than by hand:
  * the key comes only from the ``OPENROUTER_API_KEY`` environment variable and is never
    logged, cached or written anywhere;
  * every uncached call first checks a worst case (prompt tokens estimated generously, plus the
    full ``max_tokens`` of output, at the model's live price) against a persistent ledger shared by
    every run of this project; a call that could cross the cap is refused, not attempted;
  * after each call the ledger records the cost OpenRouter reports for it (``usage.cost``),
    falling back to tokens x price if the field is absent;
  * answers are cached by sha1(model + prompt), so reruns cost nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: str | Path, cap_usd: float) -> None:
        self.path = Path(path)
        self.cap = cap_usd
        self.data = {"total_usd": 0.0, "calls": 0, "by_model": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def total(self) -> float:
        return float(self.data["total_usd"])

    def max_call(self, model: str) -> float:
        return float(self.data["by_model"].get(model, {}).get("max_call_usd", 0.0))

    def check(self, worst_case: float) -> None:
        if self.total + worst_case > self.cap:
            raise BudgetExceeded(
                f"refusing call: spent ${self.total:.4f} + worst case ${worst_case:.4f} > cap ${self.cap:.2f}")

    def record(self, model: str, cost: float, tokens_in: int, tokens_out: int) -> None:
        d = self.data
        d["total_usd"] = float(d["total_usd"]) + cost
        d["calls"] = int(d["calls"]) + 1
        m = d["by_model"].setdefault(model, {"usd": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0,
                                              "max_call_usd": 0.0})
        m["max_call_usd"] = max(float(m.get("max_call_usd", 0.0)), cost)
        m["usd"] += cost
        m["calls"] += 1
        m["tokens_in"] += tokens_in
        m["tokens_out"] += tokens_out
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        tmp.replace(self.path)


def _price(model: str) -> tuple[float, float]:
    """(USD per input token, USD per output token), read live from OpenRouter's public list."""
    with urllib.request.urlopen(f"{API}/models", timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))["data"]
    for m in data:
        if m["id"] == model:
            p = m["pricing"]
            return float(p["prompt"]), float(p["completion"])
    raise ValueError(f"model {model!r} not on OpenRouter")


class OpenRouterClient:
    def __init__(self, model: str, cache_path: str | Path, ledger: Ledger,
                 max_tokens: int = 400, timeout: float = 120.0) -> None:
        self.model = model
        self.ledger = ledger
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.cache_path = Path(cache_path)
        self._cache: dict[str, str] = {}
        self._dirty = False
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self._prices: tuple[float, float] | None = None

    def _key(self, prompt: str) -> str:
        return hashlib.sha1(f"{self.model}\x00{prompt}".encode("utf-8")).hexdigest()

    def prices(self) -> tuple[float, float]:
        if self._prices is None:
            self._prices = _price(self.model)
        return self._prices

    def _post(self, body: dict) -> dict:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in the environment")
        req = urllib.request.Request(
            f"{API}/chat/completions", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def chat(self, prompt: str) -> str:
        k = self._key(prompt)
        if k in self._cache:
            return self._cache[k]
        p_in, p_out = self.prices()
        worst = (len(prompt) / 2.5 + 50) * p_in + self.max_tokens * p_out  # ~4 chars/token, padded
        # never trust the estimate alone: a call can cost more than the list price (provider
        # routing), so also allow for 1.5x the dearest call already seen for this model
        worst = max(worst, 1.5 * self.ledger.max_call(self.model))
        self.ledger.check(worst)
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "seed": 0, "max_tokens": self.max_tokens,
                "usage": {"include": True}}
        resp: dict = {}
        for attempt in range(4):
            try:
                resp = self._post(body)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt * 3)
                    continue
                raise
        usage = resp.get("usage") or {}
        t_in, t_out = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        cost = usage.get("cost")
        cost = float(cost) if cost is not None else t_in * p_in + t_out * p_out
        self.ledger.record(self.model, cost, t_in, t_out)
        text = resp["choices"][0]["message"]["content"] or ""
        self._cache[k] = text
        self._dirty = True
        return text

    def flush(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")
        self._dirty = False

    def __len__(self) -> int:
        return len(self._cache)
