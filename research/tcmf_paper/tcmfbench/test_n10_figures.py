"""N10 unit tests: Fig 4 (recall vs lambda).

Same posture as test_n09_figures.py: ``figures/make_figures.py`` lives outside the package and
is imported via sys.path. These tests check the item's own "generate from theory.py / real
scenarios and real result JSON, never hand-drawn, never hand-typed" rule, and the specific
invariants the brief calls out (the multiplicative curve has a flat region but is not flat
everywhere, and the tuned point matches its own row).

Fig 3's tests moved to ``test_n10_n11_figures.py`` when its build was reconciled with a second,
independent implementation after a Night Shift collision (see NIGHT_QUEUE.md's N10 entry) - the
second build's Fig 3 was kept, this file's original Fig 3 was not, so its tests came out too.

Run: python -m tcmfbench.test_n10_figures (or pytest tcmfbench/test_n10_figures.py)
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

_TCMF_PAPER_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper"


def _load_sweep():
    path = _TCMF_PAPER_DIR / "results_lambda_sweep" / "results_lambda_sweep.json"
    assert path.exists(), "run `python -m tcmfbench.run_lambda_sweep` to generate this file"
    return json.loads(path.read_text())


def test_fig4_sweep_data_exists_and_used_the_full_reference_protocol():
    sweep = _load_sweep()
    assert sweep["n_per_seed"] == 300
    assert sweep["seeds"] == [0, 1, 2, 3, 4]
    assert sweep["pool_size"] == 78  # N01-scale pure-regime pool
    assert "passed" in sweep["sanity_check"]


def test_fig4_grid_matches_the_committed_script_constant():
    """The committed JSON's lambda grid must be exactly `run_lambda_sweep.LAMBDA_GRID`, so the
    figure can't silently drift from the script that (re)generates it."""
    from tcmfbench import run_lambda_sweep as RLS
    sweep = _load_sweep()
    assert sweep["lambda_grid"] == RLS.LAMBDA_GRID
    assert sweep["tuned_mult_lambda"] == RLS.TUNED_MULT_LAMBDA


def test_fig4_multiplicative_curve_has_a_flat_low_lambda_region():
    """The brief's own claim, checked as a number: recall@5 at lambda<=0.3 for the
    multiplicative operator must be at or near zero - the flat region the figure shades."""
    sweep = _load_sweep()
    curve = sweep["multiplicative"]
    for lam, mean in zip(curve["lambda"], curve["mean"]):
        if lam <= 0.3:
            assert mean < 0.01, (lam, mean)


def test_fig4_multiplicative_curve_is_not_flat_everywhere():
    """The brief's explicit correction: do not imply the multiplicative operator is flat
    everywhere. It must reach a substantially higher recall by the top of the grid."""
    sweep = _load_sweep()
    curve = sweep["multiplicative"]
    assert curve["mean"][0] < 0.01
    assert curve["mean"][-1] > 0.9


def test_fig4_tuned_point_is_on_the_grid_and_matches_its_own_row():
    sweep = _load_sweep()
    idx = sweep["multiplicative"]["lambda"].index(sweep["tuned_mult_lambda"])
    grid_mean = sweep["multiplicative"]["mean"][idx]
    tuned_mean = sweep["tuned_mult_lambda_recall5"]["mean"]
    assert abs(grid_mean - tuned_mean) < 1e-9


def test_fig4_renders_to_nonempty_vector_pdf_and_png():
    sweep = _load_sweep()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig4(sweep, out / "fig4_recall_vs_lambda")
        pdf = out / "fig4_recall_vs_lambda.pdf"
        png = out / "fig4_recall_vs_lambda.png"
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
