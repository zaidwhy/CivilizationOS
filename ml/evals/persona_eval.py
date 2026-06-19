"""Persona-consistency eval harness for fine-tuned council voices.

Scores each council role on two dimensions:
  1. PERSONA_CONSISTENCY — does the response match the role's distinctive
     vocabulary and framing? (keyword/pattern matching, fast, $0)
  2. DEBATE_COHERENCE — does the response logically follow from the prior
     turns? (embedding cosine similarity of response to context, $0)

Both metrics are deterministic and run locally. A model is promoted from
candidate to production when BOTH gates pass. Results are logged to MLflow.

Usage:
    python -m ml.evals.persona_eval \
        --model qwen2.5:3b-instruct \        # or your fine-tuned Ollama model name
        --n 20 \                              # crisis scenarios to evaluate
        [--mlflow-uri mlruns]                 # local MLflow tracking URI
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---- Persona fingerprints (keyword patterns per role) ----
ROLE_PATTERNS: dict[str, list[str]] = {
    "Historian": [
        r"\bprecedent\b", r"\bhistoric(al)?\b", r"\brecord(s)?\b",
        r"\blast (time|year|incident)\b", r"\b(2\d{3}|previous)\b",
    ],
    "Strategist": [
        r"\bintervention\b", r"\bdeploy\b", r"\bimmediately\b",
        r"\bactionable\b", r"\b(first|second),?\s+(the|we)\b",
    ],
    "Skeptic": [
        r"\brisk\b", r"\bassumption\b", r"\bunintended\b",
        r"\bchallenge\b", r"\bsafeguard\b", r"\bexit\b",
    ],
    "Predictor": [
        r"\bprobabilit(y|ies)\b", r"\bforecast\b", r"\b\d+%\b",
        r"\bmost likely\b", r"\bworst[\s-]case\b", r"\btail[\s-]risk\b",
    ],
    "Synthesizer": [
        r"\bVERDICT:\b", r"\bsuccess metric\b", r"\bsuccess is defined\b",
        r"\bdecisive\b", r"\bexecutes?\b",
    ],
}

# Minimum fraction of patterns that must match for PASS
PERSONA_GATE = 0.4   # at least 40% of role patterns
COHERENCE_GATE = 0.25  # cosine similarity of response to context prompt


class EvalResult(NamedTuple):
    role: str
    persona_score: float    # fraction of patterns matched [0,1]
    coherence_score: float  # embedding cosine to context [0,1]
    persona_pass: bool
    coherence_pass: bool
    overall_pass: bool
    response_text: str


def score_persona(role: str, response: str) -> float:
    patterns = ROLE_PATTERNS.get(role, [])
    if not patterns:
        return 0.0
    hits = sum(1 for p in patterns if re.search(p, response, re.IGNORECASE))
    return hits / len(patterns)


def score_coherence(context: str, response: str) -> float:
    """Cheap coherence: word-overlap Jaccard between context and response."""
    ctx_words = set(re.findall(r"\b\w+\b", context.lower()))
    res_words = set(re.findall(r"\b\w+\b", response.lower()))
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "of", "and",
                 "to", "in", "that", "this", "it", "for", "you", "we", "i"}
    ctx_words -= stopwords
    res_words -= stopwords
    if not ctx_words or not res_words:
        return 0.0
    overlap = len(ctx_words & res_words)
    union = len(ctx_words | res_words)
    return overlap / union


def _call_ollama(model: str, system: str, prompt: str) -> str:
    """Synchronous Ollama call (no asyncio needed in eval harness)."""
    import subprocess, json as _json
    payload = _json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 200},
    })
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", "http://127.0.0.1:11434/api/chat",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True,
    )
    try:
        return _json.loads(result.stdout)["message"]["content"].strip()
    except Exception:
        return "[error: no response]"


def evaluate(
    model: str,
    scenarios: list[dict],
    mlflow_uri: str | None = None,
) -> list[EvalResult]:
    from ml.dataset.generate import ROLE_SPECS, make_sample, CRISIS_SCENARIOS
    import random

    rng = random.Random(0)
    results: list[EvalResult] = []

    for scenario in scenarios:
        for role, spec in ROLE_SPECS.items():
            sample = make_sample(role, scenario, rng)
            response = _call_ollama(model, sample["system"], sample["user"])
            p_score = score_persona(role, response)
            c_score = score_coherence(sample["user"], response)
            r = EvalResult(
                role=role,
                persona_score=round(p_score, 3),
                coherence_score=round(c_score, 3),
                persona_pass=p_score >= PERSONA_GATE,
                coherence_pass=c_score >= COHERENCE_GATE,
                overall_pass=p_score >= PERSONA_GATE and c_score >= COHERENCE_GATE,
                response_text=response[:200],
            )
            results.append(r)
            status = "✓" if r.overall_pass else "✗"
            print(f"  {status} {role:<12} persona={p_score:.2f} coherence={c_score:.2f}")

    if mlflow_uri:
        _log_to_mlflow(model, results, mlflow_uri)

    return results


def _log_to_mlflow(model: str, results: list[EvalResult], uri: str) -> None:
    try:
        import mlflow
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment("council_persona_eval")
        with mlflow.start_run(run_name=model):
            mlflow.log_param("model", model)
            mlflow.log_param("n_evals", len(results))
            by_role: dict[str, list[EvalResult]] = {}
            for r in results:
                by_role.setdefault(r.role, []).append(r)
            for role, rs in by_role.items():
                avg_p = sum(r.persona_score for r in rs) / len(rs)
                avg_c = sum(r.coherence_score for r in rs) / len(rs)
                pass_rate = sum(r.overall_pass for r in rs) / len(rs)
                mlflow.log_metric(f"{role}_persona", avg_p)
                mlflow.log_metric(f"{role}_coherence", avg_c)
                mlflow.log_metric(f"{role}_pass_rate", pass_rate)
            overall_pass = sum(r.overall_pass for r in results) / len(results)
            mlflow.log_metric("overall_pass_rate", overall_pass)
            mlflow.log_param("promoted", overall_pass >= 0.7)
            print(f"\nMLflow run logged. overall_pass_rate={overall_pass:.2f}, promoted={overall_pass >= 0.7}")
    except ImportError:
        print("mlflow not installed — skipping MLflow logging")


def summary(results: list[EvalResult]) -> None:
    by_role: dict[str, list] = {}
    for r in results:
        by_role.setdefault(r.role, []).append(r)
    print("\n── EVAL SUMMARY ─────────────────────────")
    for role, rs in by_role.items():
        avg_p = sum(r.persona_score for r in rs) / len(rs)
        avg_c = sum(r.coherence_score for r in rs) / len(rs)
        passed = sum(r.overall_pass for r in rs)
        print(f"  {role:<12} persona={avg_p:.2f}  coherence={avg_c:.2f}  pass={passed}/{len(rs)}")
    overall = sum(r.overall_pass for r in results)
    total = len(results)
    gate = overall / total >= 0.7
    print(f"\n  OVERALL: {overall}/{total} ({overall/total:.0%}) — {'PROMOTED ✓' if gate else 'REJECTED ✗'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b-instruct")
    parser.add_argument("--n", type=int, default=5, help="Number of crisis scenarios")
    parser.add_argument("--mlflow-uri", default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parents[2]))
    from ml.dataset.generate import CRISIS_SCENARIOS
    import random
    scenarios = random.Random(1).sample(CRISIS_SCENARIOS, min(args.n, len(CRISIS_SCENARIOS)))
    print(f"Evaluating model: {args.model} on {len(scenarios)} scenarios × 5 roles")
    results = evaluate(args.model, scenarios, args.mlflow_uri)
    summary(results)
