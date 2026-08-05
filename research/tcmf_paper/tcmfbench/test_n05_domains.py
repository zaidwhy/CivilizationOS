"""N05 unit tests: second-domain corpus (software-debugging, cybersecurity), authoring only.

No embedding, no Ollama, no network - a tiny deterministic fake embedder stands in for
`EmbedClient` so `generate_realtext` can be exercised structurally. Whether the two new
domains' text actually lands far/near in a real encoder's geometry is N06's job (LOCAL-ONLY);
this file only checks (a) the corpora match the existing domain contract exactly, (b) the
generated Scenario satisfies the same structural invariants every other domain does, and
(c) a lexical (word-overlap) proxy for the dissimilarity regime, which is a necessary but not
sufficient condition for the real embedding-based regime N06 must still verify.

Run: python -m tcmfbench.test_n05_domains (or pytest tcmfbench/test_n05_domains.py)
"""
from __future__ import annotations

import re

import numpy as np

from . import _bootstrap  # noqa: F401
from . import decision as D
from . import methods as M
from .realtext import DOMAINS, RealConfig, generate_realtext

NEW_DOMAIN_NAMES = ("software-debugging", "cybersecurity")

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "to", "of", "in", "on", "for", "and", "it",
    "its", "this", "that", "has", "have", "had", "at", "by", "from", "with", "into", "up", "out",
    "not", "no", "nobody", "every", "everyone", "our", "my", "i", "we", "they", "their", "been",
    "be", "being", "than", "off", "over", "under", "days", "ago", "just", "even",
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if w not in _STOPWORDS}


def _jaccard(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


class _FakeEmbedder:
    """Deterministic, offline stand-in for EmbedClient - hashes text to a small fixed vector.
    Structurally satisfies the embed()/flush() contract; carries no semantic information, so
    no test here relies on the vectors themselves, only on the Scenario's labels/text/graph."""

    def embed(self, text: str) -> list[float]:
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        return [float(x) for x in rng.normal(size=8)]

    def flush(self) -> None:
        pass


def _find_seed_for_domain(name: str, limit: int = 500) -> int:
    target_idx = next(i for i, d in enumerate(DOMAINS) if d["name"] == name)
    n = len(DOMAINS)
    for s in range(limit):
        if int(np.random.default_rng(s).integers(n)) == target_idx:
            return s
    raise AssertionError(f"no seed in [0,{limit}) selects domain {name!r}")


def test_new_domains_present_exactly_once():
    names = [d["name"] for d in DOMAINS]
    for n in NEW_DOMAIN_NAMES:
        assert names.count(n) == 1


def test_new_domains_match_the_shared_schema():
    for d in DOMAINS:
        if d["name"] not in NEW_DOMAIN_NAMES:
            continue
        assert len(d["crisis"]) == 2
        assert len(d["ancestors"]) == 3
        for anc in d["ancestors"]:
            assert set(anc.keys()) == {"event", "witness"}
            assert anc["event"] and anc["witness"]
        assert len(d["semantic_gold"]) == 2
        assert len(d["distractor"]) == 4


def test_new_domains_have_decision_tier_entries():
    for n in NEW_DOMAIN_NAMES:
        assert n in D.CANONICAL_CAUSE and D.CANONICAL_CAUSE[n]
        assert n in D.DECOY_CAUSES and len(D.DECOY_CAUSES[n]) == 3


def test_build_options_is_well_formed_for_new_domains():
    for n in NEW_DOMAIN_NAMES:
        for seed in (0, 1, 2, 17):
            options, true_idx = D.build_options(n, seed)
            assert len(options) == 4
            assert 0 <= true_idx < 4
            assert options[true_idx] == D.CANONICAL_CAUSE[n]
            # the other three are exactly the decoys, in some order
            others = [o for i, o in enumerate(options) if i != true_idx]
            assert sorted(others) == sorted(D.DECOY_CAUSES[n])


def test_generate_realtext_produces_a_well_formed_scenario_for_each_new_domain():
    cfg = RealConfig()
    embedder = _FakeEmbedder()
    for name in NEW_DOMAIN_NAMES:
        seed = _find_seed_for_domain(name)
        sc = generate_realtext(f"n05_{name}", cfg, seed, embedder)
        assert sc.domain == name

        n_anc = 3
        assert len(sc.events) == n_anc + 1  # ancestors + crisis
        assert sc.events[0].kind == "root_cause"
        assert sc.events[-1].kind == "crisis"
        assert sc.crisis_event_id == sc.events[-1].id

        # no dropout at the default config: a full chain of edges
        assert len(sc.edges) == n_anc

        labels = [m.label for m in sc.memories]
        assert labels.count("gold_root") == 1
        assert labels.count("gold_chain") == n_anc - 1
        assert labels.count("gold_semantic") == cfg.n_semantic_gold
        assert labels.count("distractor") == cfg.n_distractors
        assert labels.count("noise") == cfg.n_noise

        assert len(sc.gold_specs()) == n_anc + cfg.n_semantic_gold


def test_generate_realtext_is_deterministic_for_new_domains():
    cfg = RealConfig()
    for name in NEW_DOMAIN_NAMES:
        seed = _find_seed_for_domain(name)
        sc_a = generate_realtext("n05_det", cfg, seed, _FakeEmbedder())
        sc_b = generate_realtext("n05_det", cfg, seed, _FakeEmbedder())
        assert [ev.text for ev in sc_a.events] == [ev.text for ev in sc_b.events]
        assert [m.text for m in sc_a.memories] == [m.text for m in sc_b.memories]
        assert [m.label for m in sc_a.memories] == [m.label for m in sc_b.memories]
        assert sc_a.edges == sc_b.edges


def test_materialize_does_not_crash_on_new_domains():
    """Sanity check with the real retrieval/graph machinery (methods.materialize), still with
    the fake embedder - confirms the new scenarios are structurally usable by the rest of the
    benchmark, independent of what a real encoder would say about them."""
    cfg = RealConfig()
    for name in NEW_DOMAIN_NAMES:
        seed = _find_seed_for_domain(name)
        sc = generate_realtext(f"n05_mat_{name}", cfg, seed, _FakeEmbedder())
        mat = M.materialize(sc, cfg.max_mem_per_citizen)
        assert mat.root_id is not None
        assert len(mat.gold_ids) == 3 + cfg.n_semantic_gold
        assert len(mat.gold_causal) == 3
        assert len(mat.gold_semantic) == cfg.n_semantic_gold


def test_lexical_dissimilarity_regime_proxy():
    """A necessary-but-not-sufficient, embedding-free proxy for 'root cause is semantically far
    from the crisis, distractors are semantically near it': word-overlap with the crisis text.
    This cannot show real cosine geometry (that is N06's job, on a real encoder), but it does
    verify the corpora were authored in the intended registers - diff/forensics vocabulary for
    the causal chain, alert/pager vocabulary for the crisis and distractors - and would catch
    the class of authoring mistake where a distractor accidentally reuses root-cause wording or
    vice versa."""
    for d in DOMAINS:
        if d["name"] not in NEW_DOMAIN_NAMES:
            continue
        crisis_text = " ".join(d["crisis"])
        root_overlap = _jaccard(crisis_text, d["ancestors"][0]["event"] + " " + d["ancestors"][0]["witness"])
        distractor_overlaps = [_jaccard(crisis_text, t) for t in d["distractor"]]
        # every distractor shares more crisis vocabulary than the root cause does
        assert all(o > root_overlap for o in distractor_overlaps), (
            d["name"], root_overlap, distractor_overlaps
        )
        # the root cause shares essentially no vocabulary with the crisis surface
        assert root_overlap <= 0.05, (d["name"], root_overlap)


def test_new_domains_are_not_governance_framed_like_the_existing_six():
    """N05's stated purpose: the first six domains are all civilization/governance crises
    (budget votes, council decisions, utility boards). The two new ones must be a genuinely
    different authoring register - software/security operations - not a reskinned governance
    story, or they would not test generalization beyond the paper's one narrative."""
    # "budget" is excluded: it is a generic operational term (an on-call budget, a load-test
    # budget) that legitimately appears in a software-ops narrative too, not a governance signal
    # by itself. These are institution-specific nouns that would only show up if the text were a
    # reskin of the civilization/governance narrative.
    governance_words = {"council", "senate", "utility", "rezoned", "precinct", "treasury", "quarantine"}
    for name in NEW_DOMAIN_NAMES:
        dom = next(d for d in DOMAINS if d["name"] == name)
        text = " ".join(
            [dom["ancestors"][i][k] for i in range(3) for k in ("event", "witness")]
        ).lower()
        assert not (governance_words & _words(text)), name


if __name__ == "__main__":
    import sys
    import traceback

    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
