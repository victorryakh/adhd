"""Tiny test runner — runs all tests in this directory without pytest.

Hermes plugins ship zero-dependency tests so a smoke check works in
any environment. This file uses unittest.TestLoader to discover both
plain test_* functions and TestCase classes. It still works if
pytest is installed (the same files are picked up by `pytest tests/`).

Exit code: 0 if all pass, 1 if any fail.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent


def _ensure_path(p: Path) -> None:
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


# When run as `python tests/run_all.py`, Python does NOT load
# tests/__init__.py as a package — so do the path setup here too.
_ensure_path(PLUGIN_ROOT)
_ensure_path(TESTS_DIR)


def _load_module(name: str):
    _ensure_path(PLUGIN_ROOT)
    # tests/ must be a package; its parent dir goes on sys.path so
    # `tests.<name>` resolves correctly.
    _ensure_path(TESTS_DIR.parent)
    if name.startswith("tests.") and "tests" not in sys.modules:
        importlib.import_module("tests")
    return importlib.import_module(name)


def _discover_tests() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        module_name = f"tests.{path.stem}"
        mod = _load_module(module_name)
        suite.addTests(loader.loadTestsFromModule(mod))
    return suite


def main() -> int:
    suite = _discover_tests()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())