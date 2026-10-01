"""Tests for the frame-selection logic.

Mirrors tests/frames.test.ts. Kept deterministic by seeding random
where the original was probabilistic (it just loops enough times to
catch the rare case)."""

from __future__ import annotations

import random

from adhd_plugin.frames import PACKS, _all_frames, register_pack
from adhd_plugin.packs.core import CORE
from adhd_plugin.types_mod import Frame


# Always register the core pack before each test (in case a previous
# test cleared or mutated it).
import sys as _sys
import unittest as _unittest_mod

# Re-use unittest's TestCase so `pytest` is optional; the tests work
# the same way under pytest OR plain `python tests/run_all.py`.
_TestCase = _unittest_mod.TestCase

_orig_setup_method = _TestCase.setUp
_orig_teardown_method = _TestCase.tearDown


def setUpModule():  # noqa: N802 — unittest hook
    # Module-level setup. Not strictly needed; per-test isolation below.
    pass


class _FrameSelectionTests(_TestCase):
    def setUp(self):
        PACKS.clear()
        register_pack("core", CORE)

    def tearDown(self):
        PACKS.clear()
        register_pack("core", CORE)

    def test_core_pack_is_well_formed(self):
        # register_pack() copies to keep PACKS insulated from caller
        # mutation, so we check contents rather than identity.
        self.assertEqual(
            [f.id for f in PACKS["core"]],
            [f.id for f in CORE],
        )
        self.assertGreaterEqual(len(_all_frames()), len(CORE))
        ids = [f.id for f in CORE]
        self.assertEqual(len(set(ids)), len(ids))
        for f in CORE:
            self.assertTrue(f.id and f.label and f.prompt, f"frame {f.id} missing id/label/prompt")
            self.assertTrue(f.tags, f"frame {f.id} has no tags")
            for tag in f.tags:
                self.assertIn(tag, ("code", "design", "general", "wild"))
        # Packs with no wild frame borrow one from core, so core must keep one.
        self.assertTrue(any("wild" in f.tags for f in CORE))

    def test_select_frames_pools_from_every_pack(self):
        from adhd_plugin.frames import select_frames
        PACKS["alpha"] = [_frame("a1", ["code"]), _frame("a2", ["code"])]
        PACKS["beta"] = [_frame("b1", ["code", "wild"])]
        picked = select_frames(10, True, ["alpha", "beta"])
        self.assertEqual(_ids(picked), ["a1", "a2", "b1"])

    def test_select_frames_throws_on_unknown_pack(self):
        from adhd_plugin.frames import select_frames
        with self.assertRaises(Exception) as ctx:
            select_frames(3, True, ["core", "nope"])
        msg = str(ctx.exception)
        self.assertIn("nope", msg)
        self.assertIn("core", msg)

    def test_select_frames_borrows_core_wild_when_pool_has_none(self):
        from adhd_plugin.frames import select_frames
        PACKS["tame"] = [_frame("t1", ["code"]), _frame("t2", ["design"])]
        core_wild = [f.id for f in CORE if "wild" in f.tags]
        picked = select_frames(3, True, ["tame"])
        self.assertEqual(len(picked), 3)
        extra = [f for f in picked if f.id not in {"t1", "t2"}]
        self.assertEqual(len(extra), 1)
        self.assertIn(extra[0].id, core_wild)

    def test_code_mode_keeps_pack_whole_when_no_engineering_frame(self):
        from adhd_plugin.frames import select_frames
        PACKS["prose"] = [
            _frame("p1", ["general"]),
            _frame("p2", ["general"]),
            _frame("p3", ["wild"]),
        ]
        picked = select_frames(10, True, ["prose"])
        self.assertEqual(_ids(picked), ["p1", "p2", "p3"])

    def test_code_mode_keeps_pool_pack_whole_when_pooled_with_core(self):
        from adhd_plugin.frames import select_frames
        PACKS["prose"] = [
            _frame("p1", ["general"]),
            _frame("p2", ["general"]),
        ]
        picked = select_frames(50, True, ["core", "prose"])
        ids = {f.id for f in picked}
        self.assertIn("p1", ids)
        self.assertIn("p2", ids)

    def test_select_frames_never_returns_a_frame_twice_when_packs_share_it(self):
        from adhd_plugin.frames import select_frames
        PACKS["shared"] = list(CORE) + [_frame("s1", ["code"])]
        random.seed(42)
        for _ in range(200):
            picked = select_frames(50, False, ["core", "shared"])
            ids = [f.id for f in picked]
            self.assertEqual(len(set(ids)), len(ids))

    def test_select_frames_never_returns_a_frame_twice_when_pack_named_twice(self):
        from adhd_plugin.frames import select_frames
        random.seed(123)
        for _ in range(2000):
            picked = select_frames(10, False, ["core", "core"])
            ids = [f.id for f in picked]
            self.assertEqual(len(set(ids)), len(ids))

    def test_select_frames_throws_when_no_pack_is_named(self):
        from adhd_plugin.frames import select_frames
        with self.assertRaises(Exception) as ctx:
            select_frames(5, True, [])
        self.assertIn("at least one pack", str(ctx.exception))

    def test_only_core_remains_after_reset(self):
        self.assertEqual(list(PACKS.keys()), ["core"])


def _frame(id_: str, tags) -> Frame:
    return Frame(id=id_, label=id_, prompt=f"Think like {id_}.", tags=list(tags))


def _ids(frames):
    return sorted(f.id for f in frames)


# When pytest is available, re-export TestCase so the same file
# works under `pytest tests/`.
if "pytest" in _sys.modules:
    # Pytest picks up _FrameSelectionTests automatically. Nothing to do.
    pass