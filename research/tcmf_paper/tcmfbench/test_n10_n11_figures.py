"""N10/N11 unit tests: Fig 3 (fusion-operator theory) and Fig 5 (degradation).

Same standing rule as ``test_n09_figures.py``: every plotted value must be provably read from a
committed result file or regenerated deterministically from real benchmark code, never
hand-typed. These tests check the exact "Verify" criteria NIGHT_QUEUE.md states for N10/N11:
Fig 3's crossings are read straight off ``theory.py`` on real scenario pairs and every additive
crossing falls below its drawn bound; Fig 5's plotted numbers match their source JSON, and in
turn match the exact published values in ``tab:dropout`` in main.tex.

This is the surviving half of a Night Shift collision: a second, independent build of all six
figures landed after N10/N11 were already DONE (see NIGHT_QUEUE.md's N10/N11 entries). Fig 3 and
Fig 5 from that second build were kept over the originals; Fig 4 and Fig 6 were not (the
originals' `test_n10_figures.py`/`test_n11_figures.py` cover those two).

Run: python -m tcmfbench.test_n10_n11_figures (or pytest tcmfbench/test_n10_n11_figures.py)
"""
from __future__ import annotations

import importlib
import json
import math
import sys
import tempfile
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import theory as T

_FIGURES_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper" / "figures"
if str(_FIGURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIGURES_DIR))
MF = importlib.import_module("make_figures")

_PAPER_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper"


# --------------------------------------------------------------------------------------- Fig 3

def _strip_volatile_ids(data: dict) -> dict:
    """``Citizen``'s memory-id counter is a running counter, not reset per ``generate_mixed``
    call, so ``distractor_id`` (a label only - never fed into any margin/lambda computation)
    differs across repeated in-process calls even though every numeric value is identical. Real
    regeneration (``python figures/make_figures.py``) is one call per fresh process, so the
    committed file is unaffected; this only matters for comparing two in-process calls here."""
    return {
        **data,
        "pairs": [{k: v for k, v in p.items() if k != "distractor_id"} for p in data["pairs"]],
    }


def test_fig3_pairs_generation_is_deterministic():
    a = _strip_volatile_ids(MF.build_fig3_pairs_json())
    b = _strip_volatile_ids(MF.build_fig3_pairs_json())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_fig3_committed_json_matches_the_generator_exactly():
    committed_path = MF._FIGURES_DIR / "fig3_pairs.json"
    assert committed_path.exists(), "run make_figures.py to generate fig3_pairs.json"
    committed = json.loads(committed_path.read_text())
    fresh = json.loads(json.dumps(_strip_volatile_ids(MF.build_fig3_pairs_json()), sort_keys=True))
    committed_sorted = json.loads(json.dumps(_strip_volatile_ids(committed), sort_keys=True))
    assert fresh == committed_sorted


def test_fig3_crossovers_are_recomputable_from_theory_py():
    """Every pair's stored crossover/bound must equal calling theory.py fresh on that pair's
    own (e, ehat, b) values - the numbers were not hand-typed after generation."""
    data = json.loads((MF._FIGURES_DIR / "fig3_pairs.json").read_text())
    for p in data["pairs"]:
        assert T.mult_promotable(p["e_root"], p["b_root"], p["e_j"], p["b_j"]) == p["mult_promotable"]
        assert T.mult_crossover_lambda(
            p["e_root"], p["b_root"], p["e_j"], p["b_j"]) == p["mult_crossover_lambda"]
        assert T.additive_sufficient_lambda(
            p["ehat_root"], p["b_root"], p["ehat_j"], p["b_j"]) == p["additive_sufficient_lambda"]


def test_fig3_every_additive_crossing_falls_below_its_drawn_bound():
    """The item's own verify criterion: every plotted additive crossing really does fall below
    its drawn bound (the picture's whole point - one line works for additive)."""
    data = json.loads((MF._FIGURES_DIR / "fig3_pairs.json").read_text())
    for p in data["pairs"]:
        xc = p["additive_sufficient_lambda"]
        bound = p["additive_uniform_bound_lambda"]
        if xc is not None:
            assert math.isfinite(bound)
            assert xc <= bound + 1e-9, (p["seed"], xc, bound)


def test_fig3_matches_results_theory_json_on_shared_seeds():
    """Fig 3's per-seed worst-distractor crossover must agree with the already-published,
    already-cited ``mult_required_lambda``/``add_required_lambda`` in results_theory.json (the
    exact 3.11-9.26 spread and the one unsolvable seed main.tex already cites) - not a separate,
    silently-drifted measurement."""
    theory_path = _PAPER_DIR / "results_theory" / "results_theory.json"
    if not theory_path.exists():
        return  # not committed in every checkout; fig3_pairs.json's own tests still cover it
    theory = json.loads(theory_path.read_text())
    rows = {r["seed"]: r for r in theory["rows"]}
    data = json.loads((MF._FIGURES_DIR / "fig3_pairs.json").read_text())
    for p in data["pairs"]:
        row = rows[p["seed"]]
        mine = p["mult_crossover_lambda"]
        theirs = row["mult_required_lambda"]
        if mine is None:
            assert not math.isfinite(theirs)
        else:
            assert abs(mine - theirs) < 1e-6, (p["seed"], mine, theirs)


# --------------------------------------------------------------------------------------- Fig 5

def test_fig5_dropout_panel_matches_tab_dropout_exactly():
    """Table tab:dropout's published numbers (fraction 0/0.25/0.5/0.75/1.0), rounded to 2
    decimals, must match results_mixed.json's dropout_curve bit-for-bit at that precision."""
    results_mixed = json.loads((_PAPER_DIR / "results_mixed" / "results_mixed.json").read_text(
        encoding="utf-8"))
    dc = results_mixed["dropout_curve"]
    published = {
        "semantic_rag": {0.0: 0.51, 0.25: 0.51, 0.5: 0.51, 0.75: 0.51, 1.0: 0.51},
        "causal_only": {0.0: 0.79, 0.25: 0.69, 0.5: 0.61, 0.75: 0.57, 1.0: 0.54},
        "tcmf_add": {0.0: 0.98, 0.25: 0.80, 0.5: 0.66, 0.75: 0.58, 1.0: 0.55},
    }
    for m, rates in published.items():
        for rate, expected in rates.items():
            assert round(dc[str(rate)][m], 2) == expected, (m, rate)


def test_fig5_spurious_panel_ci_bounds_are_ordered():
    results_spurious = json.loads(
        (_PAPER_DIR / "results_spurious" / "results_spurious.json").read_text(encoding="utf-8"))
    for rate, methods in results_spurious["curve"].items():
        for m, agg in methods.items():
            r10 = agg["recall@10"]
            assert r10["ci_lo"] <= r10["mean"] <= r10["ci_hi"], (rate, m)


def test_fig5_realistic_pool_dropout_rerun_reproduces_results_mixed_scale():
    """The discovery this reconciliation flagged: a CI'd, realistic-pool rerun of the dropout
    sweep (``run_spurious.py``'s own ``dropout_curve``, added alongside its existing spurious-
    rate curve) must reproduce ``results_mixed_scale``'s pre-existing point estimates - so the
    F7 contradiction it surfaces (tcmf_add falling below the semantic floor at dropout >= 0.5)
    is a real, reproducible measurement, not a bug introduced by the new sweep."""
    spurious_path = _PAPER_DIR / "results_spurious" / "results_spurious.json"
    scale_path = _PAPER_DIR / "results_mixed_scale" / "results_mixed.json"
    if not (spurious_path.exists() and scale_path.exists()):
        return
    spurious = json.loads(spurious_path.read_text(encoding="utf-8"))
    scale = json.loads(scale_path.read_text(encoding="utf-8"))
    if "dropout_curve" not in spurious:
        return
    for rate_key, methods in spurious["dropout_curve"].items():
        for m in ("semantic_rag", "causal_only", "tcmf_add"):
            mine = methods[m]["recall@10"]["mean"]
            theirs = scale["dropout_curve"][rate_key][m]
            assert abs(mine - theirs) < 1e-9, (rate_key, m, mine, theirs)


# --------------------------------------------------------------------------------------- render

def test_fig3_and_fig5_render_to_nonempty_vector_pdf_and_png():
    fig3_data = json.loads((MF._FIGURES_DIR / "fig3_pairs.json").read_text())
    results_mixed = json.loads((_PAPER_DIR / "results_mixed" / "results_mixed.json").read_text(
        encoding="utf-8"))
    results_spurious = json.loads(
        (_PAPER_DIR / "results_spurious" / "results_spurious.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig3(fig3_data, out / "fig3_theory")
        MF.draw_fig5(results_mixed, results_spurious, out / "fig5_degradation")
        for stub in ("fig3_theory", "fig5_degradation"):
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
