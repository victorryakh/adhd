"""Frame selection — 1:1 port of src/frames.ts.

Frames push the generator into corners it wouldn't naturally go.
selectFrames picks N for a run, biased toward engineering tags when
codeMode is on, with at least one wildcard to keep range.
"""

from __future__ import annotations

import random
from typing import Dict, List, Sequence

from .types_mod import Frame, Tag


PACKS: Dict[str, List[Frame]] = {}


def register_pack(name: str, frames: Sequence[Frame]) -> None:
    """Register or replace a frame pack by name. Called from
    adhd_plugin/__init__.py on import."""
    PACKS[name] = list(frames)


def _all_frames() -> List[Frame]:
    out: List[Frame] = []
    seen: set[str] = set()
    for pack in PACKS.values():
        for f in pack:
            if f.id in seen:
                continue
            seen.add(f.id)
            out.append(f)
    return out


def _has_tag(frame: Frame, tag: Tag) -> bool:
    return tag in frame.tags


def _shuffle(arr: List[Frame]) -> List[Frame]:
    """Fisher-Yates shuffle — uniform distribution."""
    a = list(arr)
    for i in range(len(a) - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]
    return a


def select_frames(
    n: int,
    code_mode: bool = True,
    packs: Sequence[str] = ("core",),
) -> List[Frame]:
    """Pick N frames for a run. Bias toward engineering tags when
    codeMode is on, but always include at least one wildcard so
    divergence stays weird."""
    if not packs:
        raise ValueError("selectFrames needs at least one pack name")

    missing = [name for name in dict.fromkeys(packs) if name not in PACKS]
    if missing:
        raise ValueError(
            f"Unknown frame pack(s) {missing}. Available packs: "
            f"{list(PACKS.keys())}"
        )

    named_frames: List[Frame] = []
    seen: set[str] = set()
    for name in dict.fromkeys(packs):
        for f in PACKS[name]:
            if f.id not in seen:
                seen.add(f.id)
                named_frames.append(f)

    if code_mode:
        pool: List[Frame] = []
        seen_pool: set[str] = set()
        for name in dict.fromkeys(packs):
            engineering = [
                f for f in PACKS[name]
                if _has_tag(f, "code") or _has_tag(f, "design")
            ]
            chosen = engineering if engineering else list(PACKS[name])
            for f in chosen:
                if f.id not in seen_pool:
                    seen_pool.add(f.id)
                    pool.append(f)
    else:
        pool = named_frames

    wild = [
        f for f in named_frames
        if _has_tag(f, "wild")
    ]
    if not wild:
        # Borrow a wild frame from the core pack so divergence stays weird.
        core = PACKS.get("core", [])
        wild = [f for f in core if _has_tag(f, "wild")]

    shuffled = _shuffle(pool)
    picked = shuffled[: max(1, n - 1)]
    if wild:
        wild_pick = random.choice(wild)
        if not any(f.id == wild_pick.id for f in picked):
            picked.append(wild_pick)
    return picked[:n]