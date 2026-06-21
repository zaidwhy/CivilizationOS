"""PANTHEON council — five specialists debate a crisis using TCMF context.

Each council is tied to an institution (Government, Economy, etc.). When a
crisis is injected, the council's five roles speak in turn:

    Historian  → what precedents exist?
    Strategist → what should we do?
    Skeptic    → what could go wrong?
    Predictor  → what outcomes are likely?
    Synthesizer→ final policy recommendation (VERDICT)

Tier assignment (gracefully degraded by the router):
    Historians / Strategist / Skeptic / Predictor → Tier.FREE (Gemini)
    Synthesizer                                    → Tier.PREMIUM (Claude)

In $0 mode all fall through to Tier.LOCAL (Ollama).

Phase 5: institution_lens added so each institution debates through its own
mandate (law vs. markets vs. medicine vs. press vs. policing).
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


# Institution-specific mandate framing injected into every debate prompt.
INSTITUTION_LENSES: dict[str, str] = {
    "inst_gov": (
        "You advise the City Government. Your mandate is constitutional authority, "
        "public trust, democratic legitimacy, and city-wide policy. Frame solutions "
        "in terms of law, ordinance, and interagency coordination."
    ),
    "inst_economy": (
        "You advise the City Economy bureau. Your mandate is market stability, "
        "trade continuity, employment, and fiscal health. Frame solutions in terms "
        "of incentives, regulation, supply chains, and economic resilience."
    ),
    "inst_health": (
        "You advise the City Healthcare authority. Your mandate is public health, "
        "medical resource allocation, epidemiological containment, and citizen welfare. "
        "Frame solutions in terms of clinical protocols and population-level outcomes."
    ),
    "inst_media": (
        "You advise the City Media council. Your mandate is information integrity, "
        "press freedom, public messaging, and counter-disinformation. Frame solutions "
        "in terms of transparency, editorial independence, and narrative management."
    ),
    "inst_police": (
        "You advise the City Police commission. Your mandate is public safety, "
        "law enforcement, civil liberties, and community trust. Frame solutions in "
        "terms of deployment, de-escalation, legal authority, and proportionality."
    ),
}

# Role specs — each role has a distinct analytical persona.
ROLE_SPECS: list[dict] = [
    {
        "role": "Historian",
        "emoji": "📜",
        "tier": Tier.FREE,
        "system": (
            "You are the council Historian. Your job is institutional memory. "
            "Surface 1-2 specific historical precedents or past council decisions "
            "that are directly relevant to this crisis. Cite evidence from the "
            "provided memory and causal chain. Be concrete and analytical. "
            "3 sentences max. Do NOT propose solutions — that's the Strategist's job."
        ),
    },
    {
        "role": "Strategist",
        "emoji": "⚔️",
        "tier": Tier.FREE,
        "system": (
            "You are the council Strategist. Building on the Historian's precedents, "
            "propose exactly 2 actionable interventions this institution can implement "
            "within 48 hours. Be specific: WHO does WHAT, WHERE, and with WHAT authority. "
            "3 sentences max. No vague recommendations."
        ),
    },
    {
        "role": "Skeptic",
        "emoji": "🔍",
        "tier": Tier.FREE,
        "system": (
            "You are the council Skeptic. Your role is constructive challenge. "
            "Name the single biggest hidden risk or unintended consequence in the "
            "Strategist's proposals. Then propose one concrete safeguard that "
            "addresses it without abandoning the intervention entirely. "
            "3 sentences max. Be adversarial but constructive."
        ),
    },
    {
        "role": "Predictor",
        "emoji": "🔮",
        "tier": Tier.FREE,
        "system": (
            "You are the council Predictor. Given what the Historian found and the "
            "Strategist proposed: forecast the most likely outcome (with a probability "
            "estimate, e.g. '70% chance of…') and name the tail-risk worst case scenario. "
            "3 sentences max. Base your estimate on the causal precedents provided."
        ),
    },
    {
        "role": "Synthesizer",
        "emoji": "⚖️",
        "tier": Tier.PREMIUM,
        "system": (
            "You are the council Synthesizer — the final decision-maker. "
            "After hearing all four specialists, issue ONE decisive policy directive. "
            "Begin with 'VERDICT:' then state: (1) the specific action, "
            "(2) who executes it, (3) the success metric by which we will know it worked. "
            "2-3 sentences max. This verdict becomes official council policy."
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

        lens = INSTITUTION_LENSES.get(self.institution_id, f"You advise the {self.institution_name}.")
        base_prompt = (
            f"{lens}\n\n"
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
                from ..config import get_settings
                s = get_settings()
                is_synth = spec["role"] == "Synthesizer"
                if s.has_finetuned_council and not is_synth:
                    # Route all debate roles through the fine-tuned local model;
                    # Synthesizer keeps its Tier.PREMIUM path (Claude verdict).
                    effective_tier = Tier.LOCAL
                    local_model = s.ollama_council_model
                else:
                    effective_tier = spec["tier"]
                    local_model = None
                result = await router.complete(
                    prompt=user_prompt,
                    system=spec["system"],
                    tier=effective_tier,
                    max_tokens=200,
                    temperature=0.72,
                    local_model=local_model,
                )
                text = result.text.strip()[:500]
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
            await asyncio.sleep(0)


# Registry of all five councils, keyed by institution_id
COUNCILS: dict[str, Council] = {
    "inst_gov":     Council("inst_gov",     "Government"),
    "inst_media":   Council("inst_media",   "Media"),
    "inst_police":  Council("inst_police",  "Police"),
    "inst_economy": Council("inst_economy", "Economy"),
    "inst_health":  Council("inst_health",  "Healthcare"),
}
