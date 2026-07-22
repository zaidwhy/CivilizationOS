"""Downstream decision-quality experiment (REVIEW.md item W1).

Hypothesis: retrieval differences change decisions, not just ranking metrics. Each method's
top-k retrieved memories are fed to an LLM acting as a council advisor, which must pick the
true root cause of the crisis from a fixed multiple-choice set. Methods that retrieve the
causal-gold memories should score well above methods that retrieve only symptoms, and above
a no-retrieval floor.
"""
from __future__ import annotations

import re

import numpy as np

# domain -> canonical TRUE root cause (a self-inflicted governance/budget failure; matches gold_root)
CANONICAL_CAUSE = {
    "plague":  "The city government voted down emergency quarantine funding for the district.",
    "water":   "The council diverted the district's reservoir to the industrial canal.",
    "cyber":   "Budget cuts forced staff to suspend the network's security patching.",
    "crime":   "The precinct's patrol budget was cut and patrol beats were eliminated.",
    "housing": "The district was rezoned for luxury development in a closed-door deal.",
    "power":   "The utility diverted its maintenance fund to shareholder payouts.",
}

# domain -> three plausible-but-false root causes (external shocks NOT in the record)
DECOY_CAUSES = {
    "plague": [
        "Infected travelers arrived on trade caravans from a plague-struck port city.",
        "A contaminated grain shipment was distributed through the market stalls.",
        "A broken sewer main fouled the public wells near the market.",
    ],
    "water": [
        "A prolonged drought dried up the region's rivers and springs.",
        "An earthquake cracked the main water main under the district.",
        "Upstream farms drew off the river for irrigation during the dry season.",
    ],
    "cyber": [
        "A foreign state's hacking unit launched a targeted intrusion.",
        "An employee clicked a phishing email that let ransomware spread.",
        "A power surge corrupted the central servers' storage arrays.",
    ],
    "crime": [
        "A new smuggling gang moved into the district from the harbor.",
        "An economic downturn threw many residents out of work.",
        "A rival district pushed its criminals across the border into ours.",
    ],
    "housing": [
        "A surge of new migrants overwhelmed the available housing stock.",
        "A major employer left town, so landlords raised rents to cover losses.",
        "A fire destroyed several tenement blocks, displacing their tenants.",
    ],
    "power": [
        "A severe winter storm brought down the transmission lines.",
        "A lightning strike destroyed the district's main transformer.",
        "Surging demand from a heat wave overloaded the grid.",
    ],
}


def build_options(domain: str, seed: int) -> tuple[list[str], int]:
    """Build the 4-way multiple-choice option list: true cause + 3 decoys, shuffled
    deterministically. Returns (options, true_index)."""
    true_cause = CANONICAL_CAUSE[domain]
    decoys = list(DECOY_CAUSES[domain])
    options = [true_cause] + decoys
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(options))
    shuffled = [options[i] for i in order]
    true_index = int(np.where(order == 0)[0][0])
    return shuffled, true_index


def build_prompt(crisis_text: str, memory_texts: list[str], options: list[str]) -> str:
    if memory_texts:
        records = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(memory_texts))
    else:
        records = "(no relevant records were retrieved)"
    letters = ["A", "B", "C", "D"]
    opts = "\n".join(f"{letters[i]}) {o}" for i, o in enumerate(options))
    return (
        "You are an advisor to the city council. A crisis has occurred:\n"
        f"\"{crisis_text}\"\n\n"
        "Here are the records and eyewitness memories available to you:\n"
        f"{records}\n\n"
        "Based only on these records, which option best identifies the UNDERLYING ROOT CAUSE "
        "of the crisis?\n"
        f"{opts}\n\n"
        "Reply with only the single letter (A, B, C, or D) of the best-supported option.\n"
        "Answer:"
    )


def parse_letter(response: str) -> str | None:
    """Extract the chosen option letter (A-D). Robust to a chatty model.

    Note: matching is case-SENSITIVE for uppercase A-D in the fallback, because a
    case-insensitive `\\b[a-d]\\b` would match the English article "a" (very common in
    prose) and misparse. The prompt labels options with uppercase letters and asks for a
    single letter, so answers are effectively always uppercase.
    """
    if not response:
        return None
    s = response.strip()
    # 1. whole reply is just the letter, optionally wrapped: "A", "(A)", "A.", "a"
    m = re.match(r"^\(?([ABCDabcd])\)?[.:]?$", s)
    if m:
        return m.group(1).upper()
    # 2. leading letter followed by a delimiter: "A) ...", "A. ...", "A: ...", "A - ..."
    m = re.match(r"^\(?([ABCD])[)\.\:\-\s]", s)
    if m:
        return m.group(1)
    # 3. explicit phrasing: "the answer is A", "option C", "I choose D"
    m = re.search(r"(?:answer|option|choose|choice|select|pick)\W{0,15}\(?([ABCD])\b", s, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # 4. fallback: first standalone UPPERCASE A-D (case-sensitive: avoids the article "a")
    m = re.search(r"\b([ABCD])\b", s)
    if m:
        return m.group(1)
    return None


def letter_to_index(letter: str) -> int:
    return "ABCD".index(letter)


def is_correct(response: str, true_index: int) -> bool:
    letter = parse_letter(response)
    if letter is None:
        return False
    return letter_to_index(letter) == true_index
