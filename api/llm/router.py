"""The 3-tier cost-aware LLM router — the heart of CivilizationOS's budget strategy.

Every LLM call names the *highest* tier it would like. The router then serves it
with the cheapest brain that is actually available, so the whole simulation can run
at $0 during development and only spend on Claude for the showcase council debates.

    Tier.LOCAL  (0) -> Ollama (Qwen2.5 3B)        free, unlimited, on the laptop
    Tier.FREE   (1) -> Gemini Flash free tier     free quota
    Tier.PREMIUM(2) -> Claude (Haiku / Sonnet)    paid, budget-capped

Downgrade rules:
  * A PREMIUM request downgrades to FREE unless PREMIUM_MODE is on, a Claude key
    exists, and the spend cap has room.
  * A FREE request downgrades to LOCAL when no Gemini key is configured.
  * LOCAL is always available (assuming Ollama is running).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache

from ..config import Settings, get_settings

logger = logging.getLogger("civos.llm")


class Tier(IntEnum):
    LOCAL = 0
    FREE = 1
    PREMIUM = 2


# Approximate Claude pricing (USD per 1M tokens) for the budget guardrail ONLY.
# Update these from https://www.anthropic.com/pricing if rates change — the router's
# spend tracking is an estimate to protect the budget, not an invoice.
CLAUDE_PRICING: dict[str, tuple[float, float]] = {
    # model: (input_per_1m, output_per_1m)
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}


@dataclass
class LLMResult:
    text: str
    tier_requested: Tier
    tier_used: Tier
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    downgraded: bool = False


class SpendTracker:
    """Tracks estimated Claude spend this process and enforces the hard cap."""

    def __init__(self, cap_usd: float) -> None:
        self.cap_usd = cap_usd
        self.spent_usd = 0.0
        self.tier2_calls = 0

    def can_spend(self) -> bool:
        return self.spent_usd < self.cap_usd

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p_in, p_out = CLAUDE_PRICING.get(model, (0.0, 0.0))
        cost = input_tokens / 1e6 * p_in + output_tokens / 1e6 * p_out
        self.spent_usd += cost
        self.tier2_calls += 1
        logger.info(
            "Tier-2 call #%d model=%s in=%d out=%d cost=$%.4f total=$%.4f/%.2f",
            self.tier2_calls, model, input_tokens, output_tokens,
            cost, self.spent_usd, self.cap_usd,
        )
        return cost


class LLMRouter:
    """Async, lazily-initialized router over the three brains."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self.spend = SpendTracker(self.s.tier2_budget_usd)
        self._ollama = None
        self._gemini = None
        self._anthropic = None

    # ---- lazy clients (so importing the module never requires keys) ----
    def _ollama_client(self):
        if self._ollama is None:
            from ollama import AsyncClient
            self._ollama = AsyncClient(host=self.s.ollama_host)
        return self._ollama

    def _gemini_model(self):
        if self._gemini is None:
            import google.generativeai as genai
            genai.configure(api_key=self.s.gemini_api_key)
            self._gemini = genai.GenerativeModel(self.s.gemini_model)
        return self._gemini

    def _anthropic_client(self):
        if self._anthropic is None:
            from anthropic import AsyncAnthropic
            self._anthropic = AsyncAnthropic(api_key=self.s.anthropic_api_key)
        return self._anthropic

    # ---- routing ----
    def resolve_tier(self, requested: Tier) -> Tier:
        """Decide which tier actually serves a request, applying downgrade rules."""
        tier = requested
        if tier == Tier.PREMIUM:
            if not (self.s.premium_mode and self.s.has_claude and self.spend.can_spend()):
                tier = Tier.FREE
        if tier == Tier.FREE and not self.s.has_gemini:
            tier = Tier.LOCAL
        return tier

    async def complete(
        self,
        *,
        prompt: str,
        system: str = "",
        tier: Tier = Tier.LOCAL,
        max_tokens: int = 512,
        temperature: float = 0.7,
        claude_model: str | None = None,
    ) -> LLMResult:
        used = self.resolve_tier(tier)
        if used == Tier.PREMIUM:
            result = await self._complete_claude(
                prompt, system, max_tokens, temperature,
                claude_model or self.s.claude_member_model,
            )
        elif used == Tier.FREE:
            result = await self._complete_gemini(prompt, system, max_tokens, temperature)
        else:
            result = await self._complete_ollama(prompt, system, max_tokens, temperature)

        result.tier_requested = tier
        result.tier_used = used
        result.downgraded = used < tier
        return result

    async def _complete_ollama(self, prompt, system, max_tokens, temperature) -> LLMResult:
        client = self._ollama_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await client.chat(
            model=self.s.ollama_chat_model,
            messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return LLMResult(
            text=resp["message"]["content"],
            tier_requested=Tier.LOCAL, tier_used=Tier.LOCAL,
            model=self.s.ollama_chat_model,
        )

    async def _complete_gemini(self, prompt, system, max_tokens, temperature) -> LLMResult:
        model = self._gemini_model()
        full = f"{system}\n\n{prompt}" if system else prompt
        # google-generativeai is sync; keep the event loop free.
        resp = await asyncio.to_thread(
            model.generate_content,
            full,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return LLMResult(
            text=resp.text,
            tier_requested=Tier.FREE, tier_used=Tier.FREE,
            model=self.s.gemini_model,
        )

    async def _complete_claude(self, prompt, system, max_tokens, temperature, model) -> LLMResult:
        client = self._anthropic_client()
        # Honor the user's explicit, cost-driven model choice (Haiku/Sonnet).
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        cost = self.spend.record(model, in_tok, out_tok)
        return LLMResult(
            text=text,
            tier_requested=Tier.PREMIUM, tier_used=Tier.PREMIUM,
            model=model, input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings always run locally on Ollama (free). Used by the RAG layer."""
        client = self._ollama_client()
        out: list[list[float]] = []
        for t in texts:
            resp = await client.embed(model=self.s.ollama_embed_model, input=t)
            out.append(resp["embeddings"][0])
        return out


@lru_cache
def get_router() -> LLMRouter:
    return LLMRouter()
