"""Data types for the ADHD plugin — 1:1 port of src/types.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Literal, Optional, TypedDict, Union


Tag = Literal["code", "design", "general", "wild"]


@dataclass
class Frame:
    """A cognitive frame — pushes the generator into a corner it
    wouldn't naturally visit."""

    id: str
    label: str
    prompt: str  # system-prompt fragment injected into a divergent branch
    tags: List[Tag]


@dataclass
class Idea:
    """One generated idea. depth=0 for root divergence, depth>=1 for
    child ideas surfaced while deepening."""

    id: str
    frame_id: str
    text: str  # one phrase or one sentence
    rationale: Optional[str] = None
    score: Optional["Score"] = None
    depth: int = 0
    parent_id: Optional[str] = None
    cluster: Optional[str] = None


@dataclass
class Score:
    novelty: float  # 0-10, distance from the obvious
    viability: float  # 0-10, could actually ship
    fit: float  # 0-10, addresses the stated problem
    total: float  # weighted: novelty*0.35 + viability*0.40 + fit*0.25
    trap: Optional[str] = None  # specific, actionable heads-up
    strength: Optional[str] = None  # one concrete thing this idea gets right


@dataclass
class Branch:
    """One frame's raw output."""

    frame_id: str
    ideas: List[Idea] = field(default_factory=list)


@dataclass
class Cluster:
    label: str  # underlying angle, not surface keywords
    idea_ids: List[str]


@dataclass
class DeepenedIdea:
    idea_id: str
    sketch: str  # 4-8 sentences: how it works, key risk, first step
    child_ideas: List[Idea] = field(default_factory=list)


@dataclass
class RunResult:
    problem: str
    reframe: Optional[str]
    branches: List[Branch]
    clusters: List[Cluster]
    shortlist: List[Idea]
    non_obvious_pick: Optional[Idea]
    traps: List[Idea]
    deepened: List[DeepenedIdea]
    provocation: str


# RunEvent is a discriminated union surfaced through onEvent. Variants
# match src/types.ts verbatim. Python: use a class hierarchy on
# `kind`.
@dataclass
class ReframeDone:
    kind: Literal["reframe:done"] = "reframe:done"
    changed: bool = False


@dataclass
class FrameStart:
    kind: Literal["frame:start"] = "frame:start"
    frame_id: str = ""
    frame_label: str = ""


@dataclass
class FrameDone:
    kind: Literal["frame:done"] = "frame:done"
    frame_id: str = ""
    count: int = 0


@dataclass
class ScoreDone:
    kind: Literal["score:done"] = "score:done"
    total: int = 0


@dataclass
class ClusterDone:
    kind: Literal["cluster:done"] = "cluster:done"
    clusters: int = 0


@dataclass
class DeepenStart:
    kind: Literal["deepen:start"] = "deepen:start"
    idea_id: str = ""
    text: str = ""


@dataclass
class DeepenDone:
    kind: Literal["deepen:done"] = "deepen:done"
    idea_id: str = ""


@dataclass
class Warn:
    kind: Literal["warn"] = "warn"
    message: str = ""


RunEvent = Union[
    ReframeDone, FrameStart, FrameDone, ScoreDone, ClusterDone,
    DeepenStart, DeepenDone, Warn,
]


@dataclass
class RunOptions:
    problem: str
    context: Optional[str] = None  # codebase snippets, constraints, stack
    frames_per_run: int = 5
    ideas_per_frame: int = 6
    top_k: int = 3
    concurrency: int = 4
    code_mode: bool = True
    strip_anchors: bool = True
    model: Optional[str] = None  # override generator model
    critic_model: Optional[str] = None  # override critic (score + cluster)
    packs: Optional[List[str]] = None  # default ["core"]
    on_event: Optional[Callable[[RunEvent], None]] = None


# Tool argument schema (mirrors src/index.ts exported types).
class ToolArgs(TypedDict, total=False):
    problem: str
    context: Optional[str]
    frames_per_run: Optional[int]
    ideas_per_frame: Optional[int]
    top_k: Optional[int]
    concurrency: Optional[int]
    code_mode: Optional[bool]
    strip_anchors: Optional[bool]
    model: Optional[str]
    critic_model: Optional[str]
    packs: Optional[List[str]]