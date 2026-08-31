"""Put the `tools/` directory on sys.path so `import rag_ground` resolves."""

from __future__ import annotations

import sys
from pathlib import Path

# tests -> rag_ground -> tools
TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
