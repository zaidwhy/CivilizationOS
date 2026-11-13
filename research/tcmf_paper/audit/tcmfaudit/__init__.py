"""Independent adversarial benchmark for TCMF. Shares no code with ``tcmfbench``.

Importing the package puts the CivilizationOS repo root on ``sys.path`` so the deployed
retriever (``api.memory.tcmf``) can be called unmodified.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
AUDIT_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
