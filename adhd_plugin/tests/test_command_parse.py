"""Smoke test for the slash-command argument parser."""

from __future__ import annotations

import unittest

from adhd_plugin.commands import _parse_args


class _CommandParseTests(unittest.TestCase):
    def test_help_flag_returns_help(self):
        out = _parse_args("--help")
        self.assertIn("_help", out)
        self.assertNotIn("_error", out)

    def test_empty_input_is_error(self):
        out = _parse_args("")
        self.assertIn("_error", out)

    def test_problem_only(self):
        out = _parse_args('"design a retry strategy for a flaky API"')
        self.assertEqual(out.get("problem"), "design a retry strategy for a flaky API")
        self.assertFalse(out.get("json"))
        self.assertIsNone(out.get("frames_per_run"))

    def test_flags_parsed(self):
        out = _parse_args(
            '"design something" --frames 4 --ideas 8 --top 2 --concurrency 3 '
            '--no-code-mode --no-anchor-strip --pack core --pack foo --json --quiet'
        )
        self.assertEqual(out.get("problem"), "design something")
        self.assertEqual(out.get("frames_per_run"), 4)
        self.assertEqual(out.get("ideas_per_frame"), 8)
        self.assertEqual(out.get("top_k"), 2)
        self.assertEqual(out.get("concurrency"), 3)
        self.assertFalse(out.get("code_mode"))
        self.assertFalse(out.get("strip_anchors"))
        self.assertEqual(out.get("packs"), ["core", "foo"])
        self.assertTrue(out.get("json"))
        self.assertTrue(out.get("quiet"))

    def test_unknown_flag_is_error(self):
        out = _parse_args('"design something" --bogus')
        self.assertIn("_error", out)
        self.assertIn("bogus", out["_error"])

    def test_missing_flag_value_is_error(self):
        out = _parse_args('"x" --frames')
        self.assertIn("_error", out)

    def test_unquoted_problem_works(self):
        out = _parse_args("design a retry strategy")
        self.assertEqual(out.get("problem"), "design a retry strategy")

    def test_mixed_quoted_and_unquoted(self):
        out = _parse_args('"design a retry" strategy --frames 5')
        self.assertEqual(out.get("problem"), "design a retry strategy")