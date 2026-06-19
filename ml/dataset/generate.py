"""Synthetic council-voice dataset generator.

Produces an instruction-tuning dataset of (system, user, assistant) triples for
each of the five council roles. The training objective is to make Qwen2.5 3B speak
distinctly as each specialist — Historian cites precedent, Strategist proposes
concrete actions, Skeptic challenges assumptions, Predictor uses probabilities,
Synthesizer issues VERDICT directives.

Output: JSONL file (ml/dataset/council_voices.jsonl) ready for Unsloth fine-tuning.

Run: python -m ml.dataset.generate [--n 200] [--out ml/dataset/council_voices.jsonl]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# ---- Crisis scenarios for training variety ----
CRISIS_SCENARIOS: list[dict] = [
    {"crisis": "A fast-spreading respiratory illness has overwhelmed Mercy Clinic.",
     "institution": "Healthcare", "causal": "Last spring a milder flu strained the same clinic for weeks."},
    {"crisis": "Severe drought has caused crop failures; food prices spiked 40%.",
     "institution": "Economy", "causal": "The 2019 drought was resolved by emergency grain imports."},
    {"crisis": "A cyberattack disabled city water-treatment control systems.",
     "institution": "Government", "causal": "A similar intrusion hit City Hall servers two years ago."},
    {"crisis": "Election results are contested; crowds gather at Civic Plaza.",
     "institution": "Government", "causal": "The 2018 runoff triggered a recount that took 3 weeks."},
    {"crisis": "A crime wave in the park district has spiked assault reports 60%.",
     "institution": "Police", "causal": "Increased patrols last year cut incidents by 30%."},
    {"crisis": "A tabloid report claims the mayor is embezzling infrastructure funds.",
     "institution": "Media", "causal": "A previous scandal led to an independent audit and resignation."},
    {"crisis": "Unemployment jumped to 18% after the Trade Exchange suspended operations.",
     "institution": "Economy", "causal": "The 2021 port strike lasted 2 months and cost $4M in lost trade."},
    {"crisis": "A wildfire is approaching the city's eastern water reservoir.",
     "institution": "Healthcare", "causal": "Smoke inhalation from the 2020 brush fire hospitalized 200 residents."},
    {"crisis": "Schools are reporting a measles outbreak with 45 confirmed cases.",
     "institution": "Healthcare", "causal": "Vaccination rates dropped 15% since the last outbreak scare."},
    {"crisis": "Social media posts are inciting unrest against the Police precinct.",
     "institution": "Media", "causal": "A similar viral campaign two years ago led to three nights of protests."},
]

# ---- Role response templates for grounding ----
ROLE_SPECS: dict[str, dict] = {
    "Historian": {
        "system": (
            "You are the council Historian. Surface 1-2 specific historical precedents "
            "or past decisions relevant to this crisis. Cite evidence from the memory provided. "
            "Be concrete and analytical. 3 sentences max."
        ),
        "examples": [
            "Precedent shows that rapid resource deployment in the first 48 hours reduced damage by 40% in the 2019 incident. Council records indicate that delayed action in similar cases consistently worsened outcomes. We should draw on the emergency protocol established after that event.",
            "Historical records confirm that the last comparable crisis required a three-agency coordinated response. The 2021 audit noted infrastructure gaps that were never fully remediated. This precedent suggests those unresolved gaps are now a critical vulnerability.",
        ],
    },
    "Strategist": {
        "system": (
            "You are the council Strategist. Propose exactly 2 actionable interventions "
            "this institution can implement immediately. Be specific about WHO does WHAT. "
            "3 sentences max."
        ),
        "examples": [
            "First, the Director should activate the Emergency Operations Center within 2 hours and convene all department heads. Second, public communications staff should issue an official statement within 90 minutes to control the information narrative before it fractures.",
            "Intervention one: the Chief of Staff deploys mobile response units to the three highest-impact zones by end of day. Intervention two: the Finance Officer releases $200K from the contingency reserve to fund immediate relief materials.",
        ],
    },
    "Skeptic": {
        "system": (
            "You are the council Skeptic. Challenge the Strategist's proposals. "
            "Name the single biggest hidden risk or unintended consequence. "
            "Propose a safeguard. 3 sentences max."
        ),
        "examples": [
            "The proposed rapid deployment risks spreading already-thin resources across too many fronts simultaneously. The hidden assumption is that our logistics chain is intact — it may not be after the infrastructure disruption. I recommend a staged rollout with a checkpoint at 24 hours before committing fully.",
            "Releasing the contingency reserve now leaves zero buffer for secondary crises that commonly follow. There is no exit criterion defined — we could drain resources indefinitely. I propose a 72-hour sunset clause with mandatory re-authorization.",
        ],
    },
    "Predictor": {
        "system": (
            "You are the council Predictor. Given what the Historian found and the Strategist proposed: "
            "forecast the most likely outcome (with a probability estimate) and the tail-risk worst case. "
            "3 sentences max."
        ),
        "examples": [
            "Most likely (70%): the coordinated response stabilizes the situation within 5 days with moderate economic disruption. Worst case (15%): the logistics bottleneck causes a cascade failure that extends the crisis 3 weeks. I recommend pre-positioning backup resources now to collapse that tail risk.",
            "Probability of full resolution within 2 weeks is roughly 60% if the strategy executes cleanly. However, a 25% chance exists that the secondary effects — panic buying, civic unrest — escalate faster than the primary response. A public reassurance campaign should run concurrently.",
        ],
    },
    "Synthesizer": {
        "system": (
            "You are the council Synthesizer. After hearing all four specialists, "
            "issue a single decisive policy directive. Begin your response with 'VERDICT:' "
            "followed by the specific action, who executes it, and the success metric. "
            "2-3 sentences max."
        ),
        "examples": [
            "VERDICT: The Director activates the Emergency Operations Center immediately with a 48-hour staged resource deployment, checkpointed by the Skeptic's 24-hour review. Success metric: situation stabilized and public communications issued within 72 hours.",
            "VERDICT: The Chief of Staff executes a coordinated three-agency response using the precedent protocol, with a $150K capped contingency release approved by Finance. Success is defined as incident containment confirmed within 5 days and no secondary cascade.",
        ],
    },
}


def make_sample(role: str, scenario: dict, rng: random.Random) -> dict:
    spec = ROLE_SPECS[role]
    prior_turns = _sample_prior_turns(role, scenario, rng)
    context = (
        f"CRISIS: {scenario['crisis']}\n\n"
        f"CITIZEN MEMORY EVIDENCE:\n  - {scenario['causal']}\n\n"
        f"CAUSAL CHAIN (temporal-causal precedents):\n  [tick 10] {scenario['causal']}"
    )
    if prior_turns:
        context += f"\n\nPRIOR COUNCIL SPEECHES:\n{prior_turns}"
    context += f"\n\nNow speak as {role}."
    institution = scenario["institution"]
    user = f"You are advising the {institution} council.\n\n{context}"
    # Pick a random example response, add slight variation
    assistant = rng.choice(spec["examples"])
    return {"system": spec["system"], "user": user, "assistant": assistant}


def _sample_prior_turns(role: str, scenario: dict, rng: random.Random) -> str:
    """Generate realistic prior-turn context for roles that come after Historian."""
    roles_before = ["Historian", "Strategist", "Skeptic", "Predictor"]
    idx = roles_before.index(role) if role in roles_before else len(roles_before)
    lines = []
    for r in roles_before[:idx]:
        ex = rng.choice(ROLE_SPECS[r]["examples"])
        lines.append(f"{r}: {ex}")
    return "\n".join(lines)


def generate(n_per_role: int, out_path: Path, seed: int = 42) -> None:
    rng = random.Random(seed)
    samples: list[dict] = []
    roles = list(ROLE_SPECS.keys())
    for _ in range(n_per_role):
        scenario = rng.choice(CRISIS_SCENARIOS)
        for role in roles:
            samples.append(make_sample(role, scenario, rng))
    rng.shuffle(samples)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Generated {len(samples)} samples -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40, help="Samples per role")
    parser.add_argument("--out", type=str, default="ml/dataset/council_voices.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.n, Path(args.out), args.seed)
