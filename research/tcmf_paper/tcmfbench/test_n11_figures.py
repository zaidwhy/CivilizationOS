"""N11 unit tests: Fig 5 (graph degradation) + Fig 6 (decision accuracy).

Same posture as test_n09_figures.py / test_n10_figures.py: ``figures/make_figures.py`` lives
outside the package and is imported via sys.path. Both figures are a "pure plotting job" over
already-committed result JSON (results_spurious/, results_mixed_scale/, results_decision/) -
these tests check that every plotted value traces back to that source data exactly, per the
item's own verify criterion ("every plotted value matches the source JSON exactly, assert it
in the script, do not eyeball it"), and check the one new statistical primitive Fig 6 needed
(tcmfbench.stats.wilson_ci) is used correctly against the committed decision-tier data.

Run: python -m tcmfbench.test_n11_figures (or pytest tcmfbench/test_n11_figures.py)
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path

from . import _bootstrap  # noqa: F401
from .stats import wilson_ci

_FIGURES_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper" / "figures"
if str(_FIGURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIGURES_DIR))
MF = importlib.import_module("make_figures")

_TCMF_PAPER_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper"


# ------------------------------------------------------------------------------- Fig 5

def _load_spurious():
    path = _TCMF_PAPER_DIR / "results_spurious" / "results_spurious.json"
    assert path.exists(), "results_spurious/results_spurious.json missing (N04 artifact)"
    return json.loads(path.read_text())


def _load_dropout():
    path = _TCMF_PAPER_DIR / "results_mixed_scale" / "results_mixed.json"
    assert path.exists(), "results_mixed_scale/results_mixed.json missing (N01 artifact)"
    return json.loads(path.read_text())


def test_fig5_semantic_rag_is_flat_at_the_documented_floor_in_both_regimes():
    """The figure's own premise: semantic_rag never reads the causal graph, so it must be
    constant across every dropout rate and every spurious rate - the "semantic floor"."""
    spurious = _load_spurious()
    dropout = _load_dropout()
    spur_vals = {spurious["curve"][r]["semantic_rag"]["recall@10"]["mean"]
                 for r in spurious["curve"]}
    drop_vals = {dropout["dropout_curve"][r]["semantic_rag"] for r in dropout["dropout_curve"]}
    assert len(spur_vals) == 1
    assert len(drop_vals) == 1
    assert spur_vals == drop_vals  # same floor value in both source files


def test_fig5_dropout_curve_is_monotone_non_increasing_for_causal_methods():
    dropout = _load_dropout()
    keys = sorted(dropout["dropout_curve"].keys(), key=float)
    for name in ("causal_only", "tcmf_add"):
        vals = [dropout["dropout_curve"][k][name] for k in keys]
        assert all(a >= b - 1e-9 for a, b in zip(vals, vals[1:]))


def test_fig5_renders_to_nonempty_vector_pdf_and_png():
    spurious = _load_spurious()
    dropout = _load_dropout()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig5(spurious, dropout, out / "fig5_graph_degradation")
        pdf = out / "fig5_graph_degradation.pdf"
        png = out / "fig5_graph_degradation.png"
        assert pdf.stat().st_size > 500
        assert png.stat().st_size > 500
        assert pdf.read_bytes()[:4] == b"%PDF"


def test_fig5_every_plotted_method_has_a_defined_color():
    """Every method name the two source files use for Fig 5 must be in METHOD_COLORS, so the
    figure cannot silently render a method with matplotlib's default color cycle instead of
    the paper's fixed palette."""
    spurious = _load_spurious()
    dropout = _load_dropout()
    spur_methods = set(next(iter(spurious["curve"].values())).keys())
    drop_methods = set(next(iter(dropout["dropout_curve"].values())).keys())
    for name in spur_methods | drop_methods:
        assert name in MF.METHOD_COLORS, name


# ------------------------------------------------------------------------------- Fig 6

def _load_decision_source():
    path = _TCMF_PAPER_DIR / "results_decision" / "results_decision.json"
    assert path.exists(), "results_decision/results_decision.json missing"
    return json.loads(path.read_text())


def test_fig6_data_generation_is_deterministic():
    a = MF.build_fig6_data()
    b = MF.build_fig6_data()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_fig6_committed_json_matches_the_generator_exactly():
    committed_path = MF._FIGURES_DIR / "fig6_data.json"
    assert committed_path.exists(), "run make_figures.py to generate fig6_data.json"
    committed = json.loads(committed_path.read_text())
    fresh = MF.build_fig6_data()
    assert json.dumps(fresh, sort_keys=True) == json.dumps(committed, sort_keys=True)


def test_fig6_every_k_is_recovered_exactly_from_the_committed_mean():
    """decision_acc is a mean of n binary (0/1) outcomes, so mean*n must land on an integer to
    within float noise - build_fig6_data asserts this itself; this test re-derives k
    independently and checks it reproduces the source file's own mean when divided back by n."""
    src = _load_decision_source()
    data = MF.build_fig6_data()
    n = src["n"]
    for name, v in src["methods"].items():
        k = data["methods"][name]["k"]
        assert isinstance(k, int)
        assert abs(k / n - v["decision_acc"]["mean"]) < 1e-9
    for name, v in src["controls"].items():
        k = data["controls"][name]["k"]
        assert abs(k / n - v["decision_acc"]["mean"]) < 1e-9


def test_fig6_ci_matches_wilson_ci_recomputed_independently():
    """Cross-check every method's/control's committed CI against a fresh, independent call to
    tcmfbench.stats.wilson_ci on the same (k, n) - not just trusting build_fig6_data's own
    internal call to the same function."""
    data = MF.build_fig6_data()
    n = data["n"]
    for name, row in {**data["methods"], **data["controls"]}.items():
        p, lo, hi = wilson_ci(row["k"], n)
        assert abs(row["mean"] - p) < 1e-12
        assert abs(row["ci_lo"] - lo) < 1e-12
        assert abs(row["ci_hi"] - hi) < 1e-12


def test_fig6_every_ci_contains_its_own_point_estimate_and_stays_in_unit_interval():
    data = MF.build_fig6_data()
    for row in {**data["methods"], **data["controls"]}.values():
        assert 0.0 <= row["ci_lo"] <= row["mean"] <= row["ci_hi"] <= 1.0


def test_fig6_causal_leaders_clear_above_the_no_retrieval_floor():
    """The decision-tier's own headline finding (RESULTS_DECISION.md): causal-recall methods
    sit clearly above the no_retrieval floor. Checked here on the CI'd data Fig 6 actually
    draws, as a guard against a sign error or mislabeled column silently flipping the story."""
    data = MF.build_fig6_data()
    floor_hi = data["controls"]["no_retrieval"]["ci_hi"]
    for name in ("causal_only", "tcmf_add", "tcmf_shipped"):
        assert data["methods"][name]["ci_lo"] > floor_hi


def test_fig6_covers_every_method_run_decision_defines():
    data = MF.build_fig6_data()
    assert set(data["methods"].keys()) == set(MF.FIG6_ORDER)


def test_fig6_every_plotted_method_has_a_defined_color():
    for name in MF.FIG6_ORDER:
        assert name in MF.METHOD_COLORS, name


def test_fig6_renders_to_nonempty_vector_pdf_and_png():
    data = json.loads((MF._FIGURES_DIR / "fig6_data.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig6(data, out / "fig6_decision_accuracy")
        pdf = out / "fig6_decision_accuracy.pdf"
        png = out / "fig6_decision_accuracy.png"
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
