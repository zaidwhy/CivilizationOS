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

    # --- Tier 1: Gemini free tier ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- Tier 2: Anthropic Claude ---
    anthropic_api_key: str = ""
    claude_member_model: str = "claude-haiku-4-5"
    claude_synth_model: str = "claude-sonnet-4-6"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
