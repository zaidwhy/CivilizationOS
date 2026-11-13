"""Make ``tcmfaudit`` importable when pytest is started from the repository root, as CI does
(``pytest research/tcmf_paper``), and not only from this folder."""
from __future__ import annotations

import sys
from pathlib import Path

AUDIT_DIR = str(Path(__file__).resolve().parent)
if AUDIT_DIR not in sys.path:
    sys.path.insert(0, AUDIT_DIR)
