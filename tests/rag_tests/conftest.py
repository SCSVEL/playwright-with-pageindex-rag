"""Pytest configuration for adding project root to sys.path."""

import sys
from pathlib import Path

# Ensure that project root is on sys.path so we can import `src` as a package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
