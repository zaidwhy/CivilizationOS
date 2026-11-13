"""The Tier B text obeys its own authoring rules, and the reader harness scores honestly."""
from __future__ import annotations

import re

import numpy as np

from tcmfaudit import graphs
from tcmfaudit.run_decision import parse_letter
from tcmfaudit.textworld import INCIDENTS, all_texts, build, scenario_specs, wrong_root


def _fake_embeddings() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    out = {}
    for text in all_texts():
        v = rng.standard_normal(16)
        out[text] = v / np.linalg.norm(v)
    return out


def test_every_domain_has_four_complete_causes():
    assert len(INCIDENTS["domains"]) == 8
    for dom in INCIDENTS["domains"]:
        assert len(dom["causes"]) == 4 and len(dom["symptoms"]) == 5
        for cause in dom["causes"]:
            assert set(cause) == {"option", "decision", "witness", "mechanism", "mech_witness", "link"}


def test_cause_side_text_never_names_the_crisis():
    for dom in INCIDENTS["domains"]:
        pattern = re.compile("|".join(rf"\b{re.escape(k)}\b" for k in dom["keywords"]), re.I)
        for cause in dom["causes"]:
            for field in ("decision", "witness", "mechanism", "mech_witness", "option"):
                assert not pattern.search(cause[field]), (dom["id"], field, cause[field])


def test_options_do_not_copy_the_decision_text():
    for dom in INCIDENTS["domains"]:
        for cause in dom["causes"]:
            assert cause["option"].lower() not in cause["decision"].lower()


def test_no_text_is_reused_across_roles():
    texts = all_texts()
    assert len(texts) == len(set(texts))


def test_scenario_layout_and_truth():
    embed = _fake_embeddings()
    specs = scenario_specs()
    assert len(specs) == 128
    answers = []
    for spec in specs:
        for link in (False, True):
            tw = build(spec, link, embed)
            w = tw.world
            dom = INCIDENTS["domains"][spec[0]]
            assert w.n == 4 + 1 + 5 + 20 + int(link)
            assert len(w.root_gold) == 1 and len(w.causal_gold) == 2 + int(link)
            assert graphs.ancestors(graphs.oracle(w)) == {0: 1, 1: 2}
            dom = INCIDENTS["domains"][spec[0]]
            assert tw.options[tw.answer] == dom["causes"][spec[1]]["option"]
            assert w.ev_tick[1] < w.ev_tick[0] < w.ev_tick[5], "cause, mechanism, crisis in time order"
            _, wrong_text, wrong = wrong_root(tw, np.random.default_rng(1), embed)
            impostor = [c for c, _ in wrong.edges if c != 0][0]
            assert w.ev_kind[impostor] == "decoy"
            assert wrong_text[0] != tw.ev_text[0], "the wrong graph must not keep the true mechanism"
            assert wrong_text[0] in {c["mechanism"] for c in dom["causes"]}
        answers.append(tw.answer)
    counts = np.bincount(answers, minlength=4)
    assert counts.min() >= 20, f"answer position is unbalanced: {counts}"


def test_parse_letter_reads_only_a_standalone_letter():
    assert parse_letter("B") == 1
    assert parse_letter(" C.") == 2
    assert parse_letter("Answer: D") == 3
    assert parse_letter("A decision was made") == 0
    assert parse_letter("Because of it") is None
    assert parse_letter("The correct answer is C. A decision to") == 2
    assert parse_letter("The correct answer is") is None
    assert parse_letter("") is None
