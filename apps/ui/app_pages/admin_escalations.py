"""Legacy redirect to Human Review page."""

from __future__ import annotations

import runpy
from pathlib import Path

# Run human_review.py directly
target_path = Path(__file__).parent / "human_review.py"
runpy.run_path(str(target_path))
