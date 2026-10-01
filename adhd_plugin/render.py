"""Terminal renderer for RunResult — 1:1 port of src/render.ts.

Output shape (matches the original skill):
    Problem + reframe
    Wide set, by cluster, with score chips
    Converge — shortlist + non-obvious pick
    Traps (watch-outs)
    Focus — deepened branches
    Provocation

Walls of equally-weighted prose hide the good ideas — so we use
indentation, emphasis on the non-obvious pick, and small score chips.
"""

from __future__ import annotations

from typing import List

from .types_mod import Idea, RunResult


def _dim(s: str) -> str:
    return f"\x1b[2m{s}\x1b[0m"


def _bold(s: str) -> str:
    return f"\x1b[1m{s}\x1b[0m"


def _cyan(s: str) -> str:
    return f"\x1b[36m{s}\x1b[0m"


def _yellow(s: str) -> str:
    return f"\x1b[33m{s}\x1b[0m"


def _red(s: str) -> str:
    return f"\x1b[31m{s}\x1b[0m"


def _green(s: str) -> str:
    return f"\x1b[32m{s}\x1b[0m"


def _chip(i: Idea) -> str:
    if i.score is None:
        return ""
    s = i.score
    return _dim(f"[N{s.novelty:.0f} V{s.viability:.0f} F{s.fit:.0f}]")


def _strip_ansi(s: str) -> str:
    """For non-tty output (tests, --json callers)."""
    out_chars: List[str] = []
    skip = False
    for ch in s:
        if ch == "\x1b":
            skip = True
            continue
        if skip and ch == "m":
            skip = False
            continue
        if not skip:
            out_chars.append(ch)
    return "".join(out_chars)


def render_text(r: RunResult) -> str:
    out: List[str] = []

    out.append(_bold("Problem: ") + r.problem)
    if r.reframe:
        out.append(_dim(f"Reframed for divergence: {r.reframe}"))
    out.append("")

    # Wide set, by cluster.
    out.append(_bold("Wide set"))
    by_cluster: dict[str, List[Idea]] = {}
    for b in r.branches:
        for idea in b.ideas:
            key = idea.cluster or "(unclustered)"
            by_cluster.setdefault(key, []).append(idea)
    for label, ideas in by_cluster.items():
        out.append("  " + _cyan(label))
        for i in ideas:
            out.append(f"    - {i.text} {_chip(i)}")
    out.append("")

    # Converge.
    out.append(_bold("Converge — shortlist"))
    non_obvious_id = r.non_obvious_pick.id if r.non_obvious_pick is not None else None
    for i in r.shortlist:
        mark = _green("★ non-obvious pick → ") if non_obvious_id == i.id else "  "
        out.append(f"  {mark}{i.text} {_chip(i)}")
        if i.rationale:
            out.append(f"    {_dim(i.rationale)}")
        if i.score is not None and i.score.strength:
            out.append(f"    {_green('+')} {_dim(i.score.strength)}")
    out.append("")

    if r.traps:
        out.append(_bold("Traps (watch-outs, not verdicts)"))
        for t in r.traps:
            out.append(f"  {_red('⚠')} {t.text}")
            if t.score is not None and t.score.trap:
                out.append(f"    {_dim(t.score.trap)}")
            if t.score is not None and t.score.strength:
                out.append(f"    {_green('+')} {_dim(t.score.strength)}")
        out.append("")

    # Deepened — the "focus" / connecting-the-dots passes.
    out.append(_bold("Focus — deepened branches"))
    flat = [i for b in r.branches for i in b.ideas]
    for d in r.deepened:
        parent = next((i for i in flat if i.id == d.idea_id), None)
        title = parent.text if parent is not None else d.idea_id
        out.append("  " + _cyan("→ " + title))
        for ln in d.sketch.split("\n"):
            out.append("    " + ln)
        if d.child_ideas:
            out.append("    " + _dim("branches off:"))
            for c in d.child_ideas:
                tail = _dim(" — " + c.rationale) if c.rationale else ""
                out.append(f"      · {c.text}{tail}")
        out.append("")

    out.append(_bold("Provocation"))
    out.append("  " + _yellow(r.provocation))

    return "\n".join(out)