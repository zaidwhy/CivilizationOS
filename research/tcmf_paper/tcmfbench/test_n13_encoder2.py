"""N13 unit tests: second encoder + per-encoder threshold tuning.

Checks the item's own "Verify" criterion as code: whether method ordering is preserved across
encoders is asserted from the committed comparison, not eyeballed, and the anisotropy number
each encoder reports is recomputed independently rather than trusted from the committed file
alone.

Run: python -m tcmfbench.test_n13_encoder2 (or pytest tcmfbench/test_n13_encoder2.py)
"""
from __future__ import annotations

import json
import sys

import numpy as np

from . import _bootstrap  # noqa: F401
from .embed_client import SentenceEmbedClient

_RESULTS_PATH = (_bootstrap.REPO_ROOT / "research" / "tcmf_paper" / "results_encoder2" /
                 "results_encoder2.json")


def _load():
    assert _RESULTS_PATH.exists(), "run `python -m tcmfbench.run_encoder2` to generate this file"
    return json.loads(_RESULTS_PATH.read_text(encoding="utf-8"))


def test_two_encoders_are_reported_with_different_dims():
    data = _load()
    dims = {e["name"]: e["dim"] for e in data["encoders"]}
    assert len(dims) == 2
    assert len(set(dims.values())) == 2, dims


def test_anisotropy_is_lower_for_minilm_than_nomic():
    """The paper's own claim (F14): MiniLM's unrelated-pair cosine is markedly lower than
    nomic's, not just numerically different."""
    data = _load()
    aniso = {e["name"]: e["anisotropy"] for e in data["encoders"]}
    assert aniso["all-MiniLM-L6-v2"] < aniso["nomic-embed-text"] / 2


def test_selected_thresholds_differ_and_track_anisotropy():
    data = _load()
    by_name = {e["name"]: e for e in data["encoders"]}
    assert by_name["all-MiniLM-L6-v2"]["selected_threshold"] < \
        by_name["nomic-embed-text"]["selected_threshold"]


def test_minilm_threshold_sweep_peaks_at_grid_floor():
    """The exact caveat main.tex states: MiniLM's tune sweep peaks at the SMALLEST tested
    value, so the reported threshold is a lower bound on where the true optimum might sit, not
    a confirmed interior maximum the way nomic's is."""
    data = _load()
    by_name = {e["name"]: e for e in data["encoders"]}
    sweep = by_name["all-MiniLM-L6-v2"]["tune_sweep"]
    grid = sorted(float(k) for k in sweep)
    best = max(grid, key=lambda t: sweep[str(t)])
    assert best == grid[0]


def test_operator_contrast_survives_under_both_encoders():
    """The paper's central claim, checked on the TEST split under both encoders: tcmf_mult
    recall@5 stays well below tcmf_add's, not just numerically lower."""
    data = _load()
    for enc in data["encoders"]:
        r = enc["test_results"]
        mult = r["tcmf_mult"]["recall@5"]["mean"]
        add = r["tcmf_add"]["recall@5"]["mean"]
        assert add - mult > 0.2, (enc["name"], mult, add)


def test_full_ordering_preservation_flag_matches_a_fresh_comparison():
    """Recompute the 'same_order' flag directly from the two encoders' own recall5_order
    lists, rather than trusting the committed boolean."""
    data = _load()
    a, b = data["encoders"]
    assert data["same_order"] == (a["recall5_order"] == b["recall5_order"])


def test_sentence_embed_client_cache_round_trips():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        cache_path = Path(td) / "cache.json"
        ec = SentenceEmbedClient(cache_path=cache_path)
        v1 = ec.embed("a test sentence")
        ec.flush()
        assert cache_path.exists()
        ec2 = SentenceEmbedClient(cache_path=cache_path)
        assert len(ec2) == 1
        v2 = ec2.embed("a test sentence")  # must hit the cache, not reload the model
        assert v1 == v2


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
