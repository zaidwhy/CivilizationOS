"""N09 unit tests: Fig 1 (causal graph) + Fig 2 (retrieval pipeline).

``figures/make_figures.py`` lives outside the ``tcmfbench`` package (it is invoked directly,
``python research/tcmf_paper/figures/make_figures.py``, per REPRODUCE.md) so it is imported
here via ``sys.path``, not duplicated. These tests check the standing rule the item itself
states: "never hand-drawn and never hand-typed numbers" - i.e. that Fig 1's committed scenario
JSON is exactly what the generator produces (not stale, not hand-edited), that its cosine
annotations are real numbers computed from that JSON, and that Fig 2's box text is not invented
prose but a grounded paraphrase of the real ``TCMFRetriever``/``CausalGraph`` source.

Run: python -m tcmfbench.test_n09_figures (or pytest tcmfbench/test_n09_figures.py)
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path

from . import _bootstrap  # noqa: F401

_FIGURES_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper" / "figures"
if str(_FIGURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIGURES_DIR))
MF = importlib.import_module("make_figures")


def test_fig1_scenario_generation_is_deterministic():
    a = MF.build_fig1_scenario_json()
    b = MF.build_fig1_scenario_json()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_fig1_committed_json_matches_the_generator_exactly():
    """The committed ``fig1_scenario.json`` must be byte-for-byte what
    ``build_fig1_scenario_json()`` produces right now - not stale, not hand-edited. This is
    the item's own verify criterion ("Fig 1's node labels match the scenario JSON it was
    generated from") checked as code, not eyeballed."""
    committed_path = MF._FIGURES_DIR / "fig1_scenario.json"
    assert committed_path.exists(), "run make_figures.py to generate fig1_scenario.json"
    committed = json.loads(committed_path.read_text())
    fresh = json.loads(json.dumps(MF.build_fig1_scenario_json(), sort_keys=True))
    committed_sorted = json.loads(json.dumps(committed, sort_keys=True))
    assert fresh == committed_sorted


def test_fig1_causal_chain_shape_matches_config():
    data = MF.build_fig1_scenario_json()
    assert len(data["events"]) == MF.FIG1_CONFIG.chain_len
    kinds = [e["kind"] for e in data["events"]]
    assert kinds[0] == "root_cause"
    assert kinds[-1] == "crisis"
    assert len(data["edges"]) == MF.FIG1_CONFIG.chain_len - 1
    # a straight chain: root -> ... -> crisis, no branches
    edge_map = dict(data["edges"])
    assert len(edge_map) == len(data["edges"])  # every cause has exactly one recorded effect


def test_fig1_memory_label_counts_match_config():
    data = MF.build_fig1_scenario_json()
    labels = [m["label"] for m in data["memories"]]
    n_ancestors = MF.FIG1_CONFIG.chain_len - 1
    assert labels.count("gold_root") == MF.FIG1_CONFIG.witnesses_per_ancestor
    assert labels.count("gold_chain") == (n_ancestors - 1) * MF.FIG1_CONFIG.witnesses_per_ancestor
    assert labels.count("distractor") == MF.FIG1_CONFIG.n_distractors
    assert labels.count("noise") == MF.FIG1_CONFIG.n_noise == 0


def test_fig1_root_cause_is_far_distractor_is_near_by_construction():
    """The figure's headline annotation (cos(root witness, crisis) low, cos(distractor,
    crisis) high) must hold for the actual generated embeddings, not just look that way in the
    picture. Uses the same threshold (0.45) the benchmark's causal boost uses elsewhere."""
    data = MF.build_fig1_scenario_json()
    events = {e["id"]: e for e in data["events"]}
    crisis_emb = events[data["crisis_event_id"]]["embedding"]
    root_witness = next(m for m in data["memories"] if m["label"] == "gold_root")
    distractor = next(m for m in data["memories"] if m["label"] == "distractor")
    cos_root = MF._cosine(root_witness["embedding"], crisis_emb)
    cos_dist = MF._cosine(distractor["embedding"], crisis_emb)
    assert cos_root < 0.45, cos_root
    assert cos_dist > 0.45, cos_dist
    assert cos_dist > cos_root


def test_fig2_stage_text_is_grounded_in_real_source():
    """Every phrase in ``SOURCE_GROUNDING`` must be a literal substring of the file it names -
    Fig 2's box text is a legibility-motivated paraphrase of these, not invented prose."""
    for rel_path, phrases in MF.SOURCE_GROUNDING.items():
        src = (_bootstrap.REPO_ROOT / rel_path).read_text()
        for phrase in phrases:
            assert phrase in src, (rel_path, phrase)


def test_fig2_stages_cover_the_real_retrieve_pipeline():
    """Sanity-check the box labels reference the concepts they claim to, so the schematic
    cannot silently drop a pipeline stage."""
    stages = MF.FIG2_STAGES
    assert "bfs" in stages["bfs"].lower()
    assert "ancestor_id" in stages["ancestors"]
    assert "causal" in stages["causal_boost"].lower()
    assert "minmax" in stages["fusion"].lower() and "causal_boost" in stages["fusion"]
    assert all(w in stages["episodic_score"].lower() for w in ("relevance", "recency", "importance"))


def test_figures_render_to_nonempty_vector_pdf_and_png():
    data = json.loads((MF._FIGURES_DIR / "fig1_scenario.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig1(data, out / "fig1_causal_graph")
        MF.draw_fig2(out / "fig2_pipeline")
        for stub in ("fig1_causal_graph", "fig2_pipeline"):
            pdf = out / f"{stub}.pdf"
            png = out / f"{stub}.png"
            assert pdf.stat().st_size > 500
            assert png.stat().st_size > 500
            assert pdf.read_bytes()[:4] == b"%PDF"


if __name__ == "__main__":
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
