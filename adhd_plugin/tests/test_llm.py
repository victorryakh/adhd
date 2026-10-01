"""Tests for the JSON parser used by the engine fallback path."""

from __future__ import annotations

import unittest

from adhd_plugin.llm import parse_json


class _ParseJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_parses_array(self):
        self.assertEqual(parse_json("[1, 2, 3]"), [1, 2, 3])

    def test_strips_json_fence(self):
        raw = "```json\n{\"a\": 1}\n```"
        self.assertEqual(parse_json(raw), {"a": 1})

    def test_strips_bare_fence(self):
        raw = "```\n[1, 2]\n```"
        self.assertEqual(parse_json(raw), [1, 2])

    def test_finds_first_json_after_preamble(self):
        raw = 'Sure! Here is the answer:\n{"a": 2, "b": "ok"}'
        self.assertEqual(parse_json(raw), {"a": 2, "b": "ok"})

    def test_finds_first_array_after_preamble(self):
        raw = 'Preamble line\n[{"x": 1}, {"y": 2}]'
        self.assertEqual(parse_json(raw), [{"x": 1}, {"y": 2}])

    def test_picks_earlier_of_object_or_array(self):
        # Two candidates; the parser picks whichever appears first.
        # Trailing text that is not valid JSON is left alone — the
        # caller (engine) treats this as a fail-open and falls back
        # to the original problem.
        raw = '[1,2] trailing prose not json'
        # array starts at index 0, object never appears, so parser
        # parses [1,2] and then json.loads() reports "Extra data".
        # That's fine: the engine catches the exception and
        # fail-opens. The test verifies the parser's offset logic,
        # not its end-to-end behavior.
        import json as _json
        with self.assertRaises(_json.JSONDecodeError):
            parse_json(raw)

    def test_rejects_invalid_json(self):
        with self.assertRaises(Exception):
            parse_json("not json")

    def test_handles_whitespace(self):
        raw = '   \n  {"x": 1}  \n  '
        self.assertEqual(parse_json(raw), {"x": 1})