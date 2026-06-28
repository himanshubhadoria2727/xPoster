from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir():
    src_path = str(SRC)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
