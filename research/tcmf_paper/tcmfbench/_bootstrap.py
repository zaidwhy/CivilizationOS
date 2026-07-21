"""Put the CivilizationOS repo root on sys.path so ``import api...`` works when this
package is run from anywhere. Imported for its side effect."""
from __future__ import annotations

import sys
from pathlib import Path

# research/tcmf_paper/tcmfbench/_bootstrap.py -> parents[3] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

REPO_ROOT = _REPO_ROOT
