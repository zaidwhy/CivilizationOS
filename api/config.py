"""Central configuration for CivilizationOS.

Loads from environment / .env (via pydantic-settings). Every field has a safe
default so the app runs at $0 (local Ollama only) even with no .env present.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Brain routing ---
    # When False, Tier-2 (Claude) requests transparently downgrade to Tier-1/0
    # so the whole simulation runs for free during development.
    premium_mode: bool = False
    # Hard ceiling on Claude spend for this process (USD). Router refuses beyond it.
    tier2_budget_usd: float = 15.0

    # --- Tier 0: local Ollama ---
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen2.5:3b-instruct"
    ollama_embed_model: str = "nomic-embed-text"
    # Phase 4: fine-tuned council voice model (set after training + ollama create)
    ollama_council_model: str = ""  # e.g. "council-voice" — empty = use chat model

    # --- Tier 1: Gemini free tier ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- Tier 2: Anthropic Claude ---
    anthropic_api_key: str = ""
    claude_member_model: str = "claude-haiku-4-5"
    claude_synth_model: str = "claude-sonnet-4-6"

    # --- Unified OpenRouter option: one key covering both Tier.FREE (debate
    # roles) and Tier.PREMIUM (Synthesizer verdict), for deploys where Ollama
    # and separate Gemini/Claude keys aren't set up. Takes priority over
    # Gemini/Claude when configured; leave unset to keep today's behavior.
    openrouter_api_key: str = ""
    openrouter_free_model: str = ""       # serves Historian/Strategist/Skeptic/Predictor
    openrouter_premium_model: str = ""    # serves the Synthesizer verdict
    # Approximate $/1M-token cost of the two models above, for the existing
    # spend-cap guardrail (tier2_budget_usd) - OpenRouter's catalog and pricing
    # change, so this isn't looked up automatically; leave at 0.0 to track
    # tokens without enforcing a real cost cap.
    openrouter_free_price_in: float = 0.0
    openrouter_free_price_out: float = 0.0
    openrouter_premium_price_in: float = 0.0
    openrouter_premium_price_out: float = 0.0

    # --- Demo mode (public deploy) ---
    # Disables the always-on ambient loop (citizen small talk, reflection,
    # emergent auto-crises) so a public deploy doesn't call a paid API on a
    # ~1-second timer forever. Crisis injection / council debates stay fully
    # live and on-demand either way - this only gates ambient chatter.
    demo_mode: bool = False
    # Minimum seconds between POST /crisis requests, globally - stops one
    # visitor from spamming the (real-money, when OpenRouter is configured)
    # crisis-injection endpoint and burning the shared spend cap for everyone.
    crisis_cooldown_s: float = 30.0

    # --- CORS ---
    # Comma-separated list of allowed frontend origins. Defaults cover local dev;
    # add the deployed Vercel URL(s) here for the live site (see CLAUDE.md Deploy).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Simulation ---
    sim_seed: int = 42
    num_citizens: int = 10
    tick_seconds: float = 1.0  # wall-clock seconds per simulation tick

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_claude(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openrouter(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_free_model)

    @property
    def has_openrouter_premium(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_premium_model)

    @property
    def has_finetuned_council(self) -> bool:
        return bool(self.ollama_council_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
