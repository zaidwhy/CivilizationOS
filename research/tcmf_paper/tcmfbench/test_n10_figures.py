"""N10 unit tests: Fig 3 (fusion operator, affine margin vs lambda) + Fig 4 (recall vs lambda).

Same posture as test_n09_figures.py: ``figures/make_figures.py`` lives outside the package and
is imported via sys.path. These tests check the item's own "generate from theory.py / real
scenarios and real result JSON, never hand-drawn, never hand-typed" rule, and the specific
invariants the brief calls out (every additive crossing sits left of the drawn bound; the
multiplicative curve has a flat region; the sanity check against results_main_scale passed).

Run: python -m tcmfbench.test_n10_figures (or pytest tcmfbench/test_n10_figures.py)
"""
from __future__ import annotations

import importlib
import json
import math
import sys
import tempfile
from pathlib import Path

from . import _bootstrap  # noqa: F401

_FIGURES_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper" / "figures"
if str(_FIGURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIGURES_DIR))
MF = importlib.import_module("make_figures")

_TCMF_PAPER_DIR = _bootstrap.REPO_ROOT / "research" / "tcmf_paper"


# ------------------------------------------------------------------------------- Fig 3

def _strip_ids(payload: dict) -> dict:
    """`materialize()` assigns memory ids from `api/memory/stream.py`'s module-level
    `itertools.count(1)`, shared for the lifetime of the process - traced directly, not
    assumed (see the night log). So `root_id`/`distractor_id` legitimately differ between two
    `build_fig3_pairs()` calls in the same process (each call consumes the next block of ids),
    even though every numeric field is identical. Fig 1 sidesteps this by never calling
    `materialize()` at all (its own code comment says so); Fig 3 needs the real materialized
    scenario for real episodic scores and causal boosts, so instead the determinism checks
    below compare everything EXCEPT the two id fields, which are provenance-only - nothing in
    `draw_fig3` reads them."""
    rows = [{k: v for k, v in r.items() if k not in ("root_id", "distractor_id")}
            for r in payload["rows"]]
    return {**payload, "rows": rows}


def test_fig3_pair_generation_is_deterministic():
    a = MF.build_fig3_pairs()
    b = MF.build_fig3_pairs()
    assert json.dumps(_strip_ids(a), sort_keys=True) == json.dumps(_strip_ids(b), sort_keys=True)


def test_fig3_committed_json_matches_the_generator_exactly():
    """"Exactly" modulo the id-counter caveat above - see `_strip_ids`."""
    committed_path = MF._FIGURES_DIR / "fig3_pairs.json"
    assert committed_path.exists(), "run make_figures.py to generate fig3_pairs.json"
    committed = json.loads(committed_path.read_text())
    fresh = json.loads(json.dumps(_strip_ids(MF.build_fig3_pairs()), sort_keys=True))
    committed_sorted = json.loads(json.dumps(_strip_ids(committed), sort_keys=True))
    assert fresh == committed_sorted


def test_fig3_covers_all_ten_theory_seeds():
    data = MF.build_fig3_pairs()
    assert [r["seed"] for r in data["rows"]] == MF.FIG3_SEEDS
    assert len(data["rows"]) == 10


def test_fig3_only_seed_7_is_unreachable():
    """THEORY.md's recorded scope limit: exactly 1 of the 10 hardest-distractor pairs (seed 7)
    is unreachable for either operator - a boost-function defect, not a fusion defect. If this
    ever changes, that is a real finding worth its own investigation, not a silent drift."""
    data = MF.build_fig3_pairs()
    unreachable_seeds = [r["seed"] for r in data["rows"] if r["unreachable"]]
    assert unreachable_seeds == [7]
    for r in data["rows"]:
        if r["unreachable"]:
            assert r["mult_crossover_lambda"] is None
            assert r["additive_crossover_lambda"] is None
            assert r["additive_uniform_bound"] is None
            assert r["b_distractor"] >= r["b_root"]  # the actual boost-defect condition


def test_fig3_matches_results_theory_within_float_noise():
    """Cross-check against the already-committed, already-tested `results_theory/
    results_theory.json` (N15). Not bit-exact - that file's own `mult_required_lambda` iterates
    a Python `set` internally, so its tie-breaking among near-equal distractors can differ by
    hash-seed across processes; this test checks the two independent computations agree to 3
    decimal places, not that they are byte-identical."""
    ref = json.loads(
        (_TCMF_PAPER_DIR / "results_theory" / "results_theory.json").read_text())
    ref_by_seed = {r["seed"]: r for r in ref["rows"]}
    data = MF.build_fig3_pairs()
    for r in data["rows"]:
        ref_row = ref_by_seed[r["seed"]]
        if r["unreachable"]:
            assert not math.isfinite(ref_row["mult_required_lambda"])
            continue
        assert abs(r["mult_crossover_lambda"] - ref_row["mult_required_lambda"]) < 1e-3
        assert abs(r["e_root"] - ref_row["root_episodic"]) < 1e-6
        assert abs(r["b_root"] - ref_row["root_boost"]) < 1e-6


def test_fig3_every_additive_crossing_is_below_its_own_bound():
    """Proposition 2's own invariant (`theory.py`), checked on the real pairs the figure draws:
    the per-pair sufficient lambda never exceeds the episodic-score-independent uniform bound."""
    data = MF.build_fig3_pairs()
    for r in data["rows"]:
        if r["unreachable"]:
            continue
        assert r["additive_crossover_lambda"] <= r["additive_uniform_bound"] + 1e-9


def test_fig3_shipped_additive_lambda_clears_every_solvable_bound():
    """The figure's headline visual claim: the shipped additive lambda=4 sits to the right of
    (clears) every reachable pair's uniform bound - matching THEORY.md's
    `shipped_lambda_clears_additive_bound_on_all_seeds` finding."""
    data = MF.build_fig3_pairs()
    reachable = [r for r in data["rows"] if not r["unreachable"]]
    assert reachable
    worst_bound = max(r["additive_uniform_bound"] for r in reachable)
    assert MF.FIG3_SHIPPED_ADD_LAMBDA > worst_bound


def test_fig3_shipped_multiplicative_lambda_clears_no_crossing():
    """The mirror image, and the figure's other headline visual claim: the shipped
    multiplicative default (0.6) sits to the LEFT of every reachable pair's crossing point -
    none of the 9 solvable pairs are promoted at the shipped value."""
    data = MF.build_fig3_pairs()
    reachable = [r for r in data["rows"] if not r["unreachable"]]
    assert all(MF.FIG3_SHIPPED_MULT_LAMBDA < r["mult_crossover_lambda"] for r in reachable)


def test_fig3_renders_to_nonempty_vector_pdf_and_png():
    data = json.loads((MF._FIGURES_DIR / "fig3_pairs.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        MF.draw_fig3(data, out / "fig3_fusion_operator")
        pdf = out / "fig3_fusion_operator.pdf"
        png = out / "fig3_fusion_operator.png"
        assert pdf.stat().st_size > 500
        assert png.stat().st_size > 500
        assert pdf.read_bytes()[:4] == b"%PDF"


# ------------------------------------------------------------------------------- Fig 4

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
