"""PANTHEON council — five specialists debate a crisis using TCMF context.

Each council is tied to an institution (Government, Economy, etc.). When a
crisis is injected, the council's five roles speak in turn:

    Historian  → what precedents exist?
    Strategist → what should we do?
    Skeptic    → what could go wrong?
    Predictor  → what outcomes are likely?
    Synthesizer→ final policy recommendation

Tier assignment (gracefully degraded by the router):
    Historians / Strategist / Skeptic / Predictor → Tier.FREE (Gemini)
    Synthesizer                                    → Tier.PREMIUM (Claude)

In $0 mode all fall through to Tier.LOCAL (Ollama).
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

from ..llm import Tier
from ..memory.tcmf import TCMFContext

logger = logging.getLogger("civos.council")

_debate_ids = itertools.count(1)


@dataclass
class DebateTurn:
    debate_id: str
    institution_id: str
    role: str
    name: str
    text: str
    tick: int
    is_final: bool = False


# Each role gets a distinct persona injected into its system prompt.
ROLE_SPECS: list[dict] = [
    {
        "role": "Historian",
        "emoji": "📜",
        "tier": Tier.FREE,
        "system": (
            "You are the council Historian. Your job: surface relevant historical "
            "precedents, past decisions, and lessons from the city's memory. "
            "Be concise — 2-3 sentences max. Ground claims in the evidence provided."
        ),
    },
    {
        "role": "Strategist",
        "emoji": "⚔️",
        "tier": Tier.FREE,
        "system": (
            "You are the council Strategist. Your job: propose 1-2 actionable "
            "interventions the institution can take. Be specific and practical. "
            "2-3 sentences max."
        ),
    },
    {
        "role": "Skeptic",
        "emoji": "🔍",
        "tier": Tier.FREE,
        "system": (
            "You are the council Skeptic. Your job: identify the biggest risk, "
            "hidden assumption, or unintended consequence in the proposed strategies. "
            "Challenge the most confident claim. 2-3 sentences max."
        ),
    },
    {
        "role": "Predictor",
        "emoji": "🔮",
        "tier": Tier.FREE,
        "system": (
            "You are the council Predictor. Your job: forecast the most likely "
            "outcome if the proposed strategy is followed, and the worst-case if it "
            "fails. Use probabilistic language. 2-3 sentences max."
        ),
    },
    {
        "role": "Synthesizer",
        "emoji": "⚖️",
        "tier": Tier.PREMIUM,  # Claude when available
        "system": (
            "You are the council Synthesizer. You have heard the Historian, "
            "Strategist, Skeptic, and Predictor. Weigh their perspectives and issue "
            "ONE clear policy recommendation the institution should adopt. "
            "Start with 'VERDICT:' then 1-2 sentences."
        ),
    },
]


class Council:
    """A five-specialist debate council for one institution."""

    def __init__(self, institution_id: str, institution_name: str) -> None:
        self.institution_id = institution_id
        self.institution_name = institution_name

    async def deliberate(
        self,
        ctx: TCMFContext,
        router,
    ) -> AsyncIterator[DebateTurn]:
        """Yields DebateTurns as each specialist responds. Streams live."""
        debate_id = f"d{next(_debate_ids)}"
        transcript: list[str] = []

        base_prompt = (
            f"You are advising the {self.institution_name} council.\n\n"
            f"{ctx.context_text}"
        )

        for spec in ROLE_SPECS:
            role = spec["role"]
            prior = "\n".join(
                f"{ROLE_SPECS[i]['role']}: {t}" for i, t in enumerate(transcript)
            )
            if prior:
                user_prompt = (
                    f"{base_prompt}\n\n"
                    f"PRIOR COUNCIL SPEECHES:\n{prior}\n\n"
                    f"Now speak as {role}."
                )
            else:
                user_prompt = f"{base_prompt}\n\nSpeak as {role}."

            try:
                result = await router.complete(
                    prompt=user_prompt,
                    system=spec["system"],
                    tier=spec["tier"],
                    max_tokens=120,
                    temperature=0.75,
                )
                text = result.text.strip().split("\n")[0][:300]
            except Exception:
                logger.exception("council %s/%s failed", self.institution_id, role)
                text = f"[{role} unavailable]"

            transcript.append(text)
            turn = DebateTurn(
                debate_id=debate_id,
                institution_id=self.institution_id,
                role=role,
                name=f"{spec['emoji']} {role}",
                text=text,
                tick=ctx.tick,
                is_final=(role == "Synthesizer"),
            )
            yield turn
            # small yield so the event loop breathes between LLM calls
            await asyncio.sleep(0)


# Registry of all five councils, keyed by institution_id
COUNCILS: dict[str, Council] = {
    "inst_gov":     Council("inst_gov",     "Government"),
    "inst_media":   Council("inst_media",   "Media"),
    "inst_police":  Council("inst_police",  "Police"),
    "inst_economy": Council("inst_economy", "Economy"),
    "inst_health":  Council("inst_health",  "Healthcare"),
}
