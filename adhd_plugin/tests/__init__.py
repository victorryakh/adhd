"""Minimal test suite for the ADHD plugin.

Focus: the pure-logic surfaces that don't touch ctx.llm (frame
selection, JSON parsing). The engine, tools, and slash command
handler are covered by lighter smoke tests that stub out ctx.

Run from the plugin root:
    python -m pytest tests/ -v

Or, without pytest:
    python -m tests.run_all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the adhd_plugin package importable when running this file in
# isolation. pytest's conftest handles this for `pytest tests/`, but
# `python -m tests.run_all` needs an explicit path setup.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))