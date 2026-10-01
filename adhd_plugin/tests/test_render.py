"""Tests for the renderer — exercises both the ANSI path and the
strip-ansi path, and verifies the output shape matches the original
src/render.ts."""

from __future__ import annotations

import unittest

from adhd_plugin.render import _strip_ansi, render_text
from adhd_plugin.types_mod import Branch, Cluster, DeepenedIdea, Idea, RunResult, Score


def _idea(
    id_: str = "i1",
    text: str = "An idea",
    frame: str = "hardware-eyes",
    score: Score | None = None,
    cluster: str | None = None,
) -> Idea:
    return Idea(id=id_, frame_id=frame, text=text, score=score, cluster=cluster)


def _score(novelty=7, viability=8, fit=9, total=None, trap=None, strength=None) -> Score:
    if total is None:
        total = novelty * 0.35 + viability * 0.40 + fit * 0.25
    return Score(novelty=novelty, viability=viability, fit=fit, total=total,
                 trap=trap, strength=strength)


class _RenderTests(unittest.TestCase):
    def test_renders_minimal_result(self):
        r = RunResult(
            problem="Design a CLI retry strategy",
            reframe=None,
            branches=[Branch(frame_id="hardware-eyes", ideas=[
                _idea("i1", "Bus topology solution", score=_score()),
            ])],
            clusters=[],
            shortlist=[],
            non_obvious_pick=None,
            traps=[],
            deepened=[],
            provocation="What if we took this seriously: Bus topology solution",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("Problem: Design a CLI retry strategy", plain)
        self.assertIn("Wide set", plain)
        self.assertIn("Bus topology solution", plain)
        self.assertIn("Provocation", plain)

    def test_renders_reframe_when_present(self):
        r = RunResult(
            problem="x",
            reframe="the underlying job",
            branches=[Branch(frame_id="hardware-eyes", ideas=[])],
            clusters=[],
            shortlist=[],
            non_obvious_pick=None,
            traps=[],
            deepened=[],
            provocation="?",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("Reframed for divergence: the underlying job", plain)

    def test_renders_clusters_in_wide_set(self):
        r = RunResult(
            problem="x",
            reframe=None,
            branches=[Branch(frame_id="hardware-eyes", ideas=[
                _idea("a", "first", cluster="cluster A", score=_score()),
                _idea("b", "second", cluster="cluster A", score=_score()),
                _idea("c", "third", score=_score()),
            ])],
            clusters=[Cluster(label="cluster A", idea_ids=["a", "b"])],
            shortlist=[],
            non_obvious_pick=None,
            traps=[],
            deepened=[],
            provocation="?",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("cluster A", plain)
        self.assertIn("(unclustered)", plain)

    def test_shortlist_marks_non_obvious_pick(self):
        i1 = _idea("a", "obvious one", score=_score(novelty=4, viability=9, fit=10))
        i2 = _idea("b", "weird one", score=_score(novelty=10, viability=7, fit=7))
        r = RunResult(
            problem="x",
            reframe=None,
            branches=[Branch(frame_id="hardware-eyes", ideas=[i1, i2])],
            clusters=[],
            shortlist=[i1, i2],
            non_obvious_pick=i2,
            traps=[],
            deepened=[],
            provocation="?",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("non-obvious pick", plain)
        self.assertIn("weird one", plain)

    def test_renders_traps_section_when_present(self):
        trap = _idea("t", "trap idea", score=_score(trap="looks great but breaks at 10k"))
        r = RunResult(
            problem="x",
            reframe=None,
            branches=[Branch(frame_id="hardware-eyes", ideas=[trap])],
            clusters=[],
            shortlist=[],
            non_obvious_pick=None,
            traps=[trap],
            deepened=[],
            provocation="?",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("Traps", plain)
        self.assertIn("looks great but breaks at 10k", plain)

    def test_renders_deepened_sketches(self):
        idea = _idea("i1", "winner", score=_score())
        d = DeepenedIdea(
            idea_id="i1",
            sketch="Multi\nline\nsketch.",
            child_ideas=[_idea("c1", "child thought")],
        )
        r = RunResult(
            problem="x",
            reframe=None,
            branches=[Branch(frame_id="hardware-eyes", ideas=[idea])],
            clusters=[],
            shortlist=[idea],
            non_obvious_pick=idea,
            traps=[],
            deepened=[d],
            provocation="?",
        )
        text = render_text(r)
        plain = _strip_ansi(text)
        self.assertIn("Focus — deepened branches", plain)
        self.assertIn("winner", plain)
        self.assertIn("Multi", plain)
        self.assertIn("child thought", plain)