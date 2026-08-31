"""Put the `tools/` directory on sys.path so `import inj_bench` resolves."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

os.environ.setdefault("RAG_EMBEDDING_BACKEND", "hash")
