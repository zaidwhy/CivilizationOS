#!/usr/bin/env python3
"""
Generate synthetic council voice training data using Claude Haiku.

Each scenario produces 5 samples (one per council role) in the same
format as ml/dataset/council_voices.jsonl. The script appends to the
output file so it's safe to run multiple times.

Usage:
    python ml/generate_dataset.py                          # 30 scenarios (~150 samples)
    python ml/generate_dataset.py --scenarios 60           # 60 scenarios (~300 samples)
    python ml/generate_dataset.py --out path/to/file.jsonl
    python ml/generate_dataset.py --dry-run               # print first scenario, no API calls
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

import anthropic

# --------------------------------------------------------------------------- #
# Role system prompts — must match what train_lora.ipynb expects              #
# --------------------------------------------------------------------------- #
ROLE_SYSTEMS: dict[str, str] = {
    "Historian": (
        "You are the council Historian. Surface 1-2 specific historical precedents or "
        "past decisions relevant to this crisis. Cite evidence from the memory provided. "
        "Be concrete and analytical. 3 sentences max."
    ),
    "Strategist": (
        "You are the council Strategist. Propose exactly 2 actionable interventions this "
        "institution can implement immediately. Be specific about WHO does WHAT. 3 sentences max."
    ),
    "Skeptic": (
        "You are the council Skeptic. Identify exactly 1 unchallenged assumption and "
        "1 systemic risk in the proposed interventions. Propose one safeguard. 3 sentences max."
    ),
    "Predictor": (
        "You are the council Predictor. Given what the Historian found and the Strategist "
        "proposed: forecast the most likely outcome (with a probability estimate) and the "
        "tail-risk worst case. 3 sentences max."
    ),
    "Synthesizer": (
        "You are the council Synthesizer. Based on ALL council arguments, issue a crisp "
        "binding VERDICT: one concrete action, one success metric, one contingency. "
        "Start with 'VERDICT:'. 4 sentences max."
    ),
}

ROLES = ["Historian", "Strategist", "Skeptic", "Predictor", "Synthesizer"]

# --------------------------------------------------------------------------- #
# Crisis scenario bank                                                         #
# --------------------------------------------------------------------------- #
SCENARIOS: list[dict[str, str]] = [
    # Healthcare
    {"institution": "Healthcare", "crisis": "An unidentified fever is spreading through the residential district; three deaths reported in 48 hours.", "memory": "A similar fever cluster six years ago was traced to a contaminated water main serving the east ward."},
    {"institution": "Healthcare", "crisis": "Clinic staff have walked out on strike during peak flu season, leaving the city with one doctor on duty.", "memory": "The last staff walkout in 2019 lasted 11 days and created a patient backlog that took three months to clear."},
    {"institution": "Healthcare", "crisis": "A batch of contaminated cooking oil from a market vendor has caused 40 hospitalizations.", "memory": "Foodborne illness from the 2021 street market outbreak resulted in two fatalities and a $2M liability claim."},
    {"institution": "Healthcare", "crisis": "Mental health emergency admissions have tripled following a wave of factory closures.", "memory": "After the textile factory closure in 2018, suicide rates rose 18% in the affected district."},
    {"institution": "Healthcare", "crisis": "A rare tropical disease has been confirmed in a traveller, raising fears of local transmission.", "memory": "The 2016 imported disease scare required 90-day quarantine protocols and cost the city $800K in containment."},
    # Government
    {"institution": "Government", "crisis": "The main freight bridge has partially collapsed, blocking the primary supply route into the city.", "memory": "A bridge inspection 18 months ago flagged critical corrosion in the central support pylons, but repairs were deferred."},
    {"institution": "Government", "crisis": "The water treatment plant has failed; residents in three districts have no safe drinking water.", "memory": "A smaller treatment plant failure in 2020 took six days to repair and required emergency water tanker imports."},
    {"institution": "Government", "crisis": "A projected $40M budget deficit is forcing cuts to essential public services.", "memory": "The 2017 austerity programme triggered a civic workers strike that cost more to resolve than the savings it achieved."},
    {"institution": "Government", "crisis": "A senior city official has been arrested on bribery charges during an ongoing infrastructure audit.", "memory": "Previous corruption scandals in 2019 resulted in project delays of 18+ months and triggered a federal oversight review."},
    {"institution": "Government", "crisis": "A construction contractor has been found falsifying safety certifications on three public buildings.", "memory": "A similar fraud in 2014 led to a building collapse and $12M in damages plus criminal prosecutions."},
    {"institution": "Government", "crisis": "An extreme heatwave is overloading the power grid; rolling blackouts are beginning across residential zones.", "memory": "The 2022 summer blackout lasted 19 hours and led to four heat-related deaths among elderly residents."},
    # Economy
    {"institution": "Economy", "crisis": "The city's largest employer has announced 1,200 redundancies effective next month.", "memory": "The last mass layoff event in 2020 caused a 14% drop in local retail spending that persisted for two quarters."},
    {"institution": "Economy", "crisis": "A social media rumour about bank insolvency has triggered a run; citizens are queueing to withdraw savings.", "memory": "A smaller bank scare in 2018 was quelled within 72 hours by a public statement from the Reserve Committee."},
    {"institution": "Economy", "crisis": "A foreign competitor is undercutting local market prices by 40%, threatening to collapse small traders.", "memory": "Predatory pricing by an outside chain in 2016 shuttered 34 independent shops in the market district."},
    {"institution": "Economy", "crisis": "A port blockade has disrupted supply chains; essential goods are expected to run short in 10 days.", "memory": "The 2021 logistics strike created shortages that took three weeks to resolve and drove inflation up 7%."},
    {"institution": "Economy", "crisis": "A fraudulent cryptocurrency scheme has wiped out the life savings of hundreds of citizens.", "memory": "A similar Ponzi scheme in 2020 affected 800 residents and resulted in only 12% recovery of lost funds."},
    # Media
    {"institution": "Media", "crisis": "A deepfake video of the mayor endorsing a banned faction has gone viral and is inciting unrest.", "memory": "A manipulated audio clip during the 2022 election campaign took four days to debunk and shifted polling by 9 points."},
    {"institution": "Media", "crisis": "A local newspaper has published allegations of a police cover-up in an unsolved missing-person case.", "memory": "A previous media-police conflict in 2019 damaged public trust and led to a 30% drop in crime tip-offs."},
    {"institution": "Media", "crisis": "Foreign-state actors are running a coordinated disinformation campaign targeting the city council elections.", "memory": "The 2021 foreign influence operation was not detected until after election day, influencing an estimated 8% of votes."},
    {"institution": "Media", "crisis": "A whistleblower has leaked documents proving a major housing developer bribed planning officials.", "memory": "Previous corruption exposés without proper source protection resulted in prosecution of the whistleblower rather than the offender."},
    {"institution": "Media", "crisis": "Coordinated bot accounts are spreading false claims that the pandemic vaccines caused deaths at the clinic.", "memory": "During the 2020 vaccine rollout, misinformation reduced uptake by 22% in the south ward until corrective messaging launched."},
    # Police
    {"institution": "Police", "crisis": "An officer-involved shooting of an unarmed citizen has sparked protests outside the precinct.", "memory": "A similar incident in 2021 escalated into three nights of unrest before a community mediation panel de-escalated tensions."},
    {"institution": "Police", "crisis": "A drug trafficking ring has been discovered operating out of the warehouse district and is resisting arrest.", "memory": "The 2019 warehouse district operation required multi-agency coordination and resulted in 47 arrests over two weeks."},
    {"institution": "Police", "crisis": "Coordinated retail theft via encrypted social media channels has cost market traders $300K this month.", "memory": "A similar organised theft ring in 2022 was broken only after undercover surveillance over six weeks."},
    {"institution": "Police", "crisis": "A child went missing from the school district three days ago; national media attention is escalating pressure.", "memory": "Previous missing-child cases where media was managed proactively saw faster resolution than those that became media circuses."},
    {"institution": "Police", "crisis": "A gang war over territory in the east district has resulted in two shootings in 24 hours.", "memory": "The 2018 gang conflict required a 90-day surge deployment and a community outreach programme to restore stability."},
    # Cross-institutional
    {"institution": "Government", "crisis": "An anonymous bomb threat has caused mass evacuation of the city centre during peak business hours.", "memory": "A false bomb scare in 2020 cost the economy $4M in lost trade and required 200 officer-hours to clear."},
    {"institution": "Healthcare", "crisis": "A toxic chemical spill from an overturned lorry is spreading fumes through the residential quarter.", "memory": "A 2017 chemical spill required full evacuation of 600 residents and took 18 hours to neutralise."},
    {"institution": "Economy", "crisis": "The city's main shopping precinct has been shuttered after a structural survey found unsafe foundations.", "memory": "The last forced closure of a commercial zone in 2019 caused a 6-week revenue gap that bankrupted 12 businesses."},
    {"institution": "Government", "crisis": "A wildfire is burning on the city's eastern boundary; evacuation of outer suburbs is being considered.", "memory": "The 2023 eastern fire required evacuation of 4,000 residents and took 11 days to fully contain."},
    {"institution": "Police", "crisis": "A large unauthorised protest has blocked the main arterial road and is refusing to disperse.", "memory": "The 2022 road blockade that lasted over 24 hours cost the city $1.8M in diverted traffic and emergency response."},
]


def build_user_prompt(
    institution: str,
    crisis: str,
    memory: str,
    role: str,
    prior_speeches: dict[str, str],
    tick: int,
) -> str:
    lines = [
        f"You are advising the {institution} council.",
        "",
        f"CRISIS: {crisis}",
        "",
        "CITIZEN MEMORY EVIDENCE:",
        f"  - {memory}",
        "",
        "CAUSAL CHAIN (temporal-causal precedents):",
        f"  [tick {tick}] {memory}",
    ]
    if prior_speeches:
        lines += ["", "PRIOR COUNCIL SPEECHES:"]
        for r, speech in prior_speeches.items():
            lines.append(f"{r}: {speech}")
    lines += ["", f"Now speak as {role}."]
    return "\n".join(lines)


def call_haiku(client: anthropic.Anthropic, system: str, user: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text.strip()
        except anthropic.RateLimitError:
            if attempt < retries:
                time.sleep(10)
            else:
                raise
        except Exception:
            if attempt < retries:
                time.sleep(2)
            else:
                raise
    return ""


def generate_scenario(
    client: anthropic.Anthropic,
    scenario: dict[str, str],
    dry_run: bool = False,
) -> list[dict[str, str]]:
    institution = scenario["institution"]
    crisis = scenario["crisis"]
    memory = scenario["memory"]
    tick = random.randint(5, 60)

    samples: list[dict[str, str]] = []
    prior_speeches: dict[str, str] = {}

    for role in ROLES:
        system = ROLE_SYSTEMS[role]
        user = build_user_prompt(institution, crisis, memory, role, prior_speeches, tick)

        if dry_run:
            print(f"\n{'─'*60}")
            print(f"ROLE: {role}")
            print(f"SYSTEM: {system[:80]}…")
            print(f"USER:\n{user}")
            assistant = f"[DRY RUN — no API call for {role}]"
        else:
            assistant = call_haiku(client, system, user)
            time.sleep(0.3)  # stay well under rate limits

        samples.append({"system": system, "user": user, "assistant": assistant})
        prior_speeches[role] = assistant

    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate council voice training data via Claude Haiku")
    parser.add_argument("--scenarios", type=int, default=30, help="Number of scenarios to generate (default 30)")
    parser.add_argument("--out", default="ml/dataset/council_voices.jsonl", help="Output JSONL file")
    parser.add_argument("--dry-run", action="store_true", help="Print first scenario without making API calls")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        raise SystemExit("ANTHROPIC_API_KEY not set. Add it to .env and restart the shell.")

    client = anthropic.Anthropic(api_key=api_key or "dry-run")

    # Sample scenarios (repeating bank if --scenarios > len(SCENARIOS))
    pool = SCENARIOS * ((args.scenarios // len(SCENARIOS)) + 1)
    random.shuffle(pool)
    selected = pool[: args.scenarios]

    total_written = 0
    with out_path.open("a", encoding="utf-8") as f:
        for i, scenario in enumerate(selected):
            print(f"[{i+1}/{len(selected)}] {scenario['institution']} — {scenario['crisis'][:60]}…")
            samples = generate_scenario(client, scenario, dry_run=args.dry_run)
            if not args.dry_run:
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                total_written += len(samples)
                f.flush()
            if args.dry_run:
                break  # only show first scenario in dry-run mode

    if not args.dry_run:
        existing = sum(1 for _ in out_path.open(encoding="utf-8"))
        print(f"\nDone. Added {total_written} samples. File now has {existing} total samples.")
        print(f"Output: {out_path.resolve()}")


if __name__ == "__main__":
    main()
