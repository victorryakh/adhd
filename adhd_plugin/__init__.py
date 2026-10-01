"""ADHD — Hermes Agent plugin entrypoint.

Adapts victorryakh/adhd (originally a Node CLI built on the Claude Agent
SDK) to a native Hermes Agent plugin:

- LLM traffic goes through ctx.llm.acomplete / acomplete_structured.
  No SDK dependency, no API keys handled by the plugin, no direct HTTP.
- The four-phase diverge → score+cluster → deepen loop is preserved
  1:1 (see engine.py).
- Frame selection (frames.py + packs/core.py) is pure Python with the
  15 core frames copied verbatim.
- Output renders identically (render.py).
- The user-facing surface is:
    - /adhd "<problem>" [--flags] slash command (commands.py)
    - adhd.run tool (tools.py)
    - the adhd bundled skill (skills/adhd/SKILL.md)

Run-config defaults (frames_per_run=5, ideas_per_frame=6, ...) live
in plugin.yaml under config_schema and are read via ctx.get_config().
The plugin only overrides them at request time when the user passes
explicit flags — defaults from config are applied by the slash /
tool handlers before constructing RunOptions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


# Built-in pack is registered at import time so the engine has frames
# to draw from before ctx.register() runs.
from . import frames as _frames  # noqa: E402
from .packs.core import CORE  # noqa: E402


_frames.register_pack("core", CORE)


def _apply_config_defaults(opts: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Fill opts from config_schema values the user didn't override."""
    if ctx is None:
        return opts
    cfg_map = {
        "frames_per_run": ("int", 5),
        "ideas_per_frame": ("int", 6),
        "top_k": ("int", 3),
        "concurrency": ("int", 4),
        "code_mode": ("bool", True),
        "strip_anchors": ("bool", True),
        "default_pack": ("str", "core"),
    }
    for key, (kind, default) in cfg_map.items():
        if opts.get(key) is not None:
            continue
        try:
            value = ctx.get_config(key, default=default)
        except Exception:
            value = default
        if value is None:
            value = default
        opts[key] = value
    # If the user didn't pass packs, use the configured default_pack.
    if not opts.get("packs"):
        opts["packs"] = [opts["default_pack"]]
    return opts


async def _adhd_command_handler(ctx: Any, raw_args: str) -> str:
    from .commands import handle_adhd
    return await handle_adhd(ctx, raw_args)


async def _adhd_run_tool_handler(args: dict, **kwargs) -> str:
    """Tool handler signature: def(args: dict, **kwargs) -> str.

    Hermes injects ctx via kwargs in some contexts (e.g. dispatch
    from a slash command); for direct tool calls the host wires
    ctx.llm into a context that's accessible through kwargs. We
    normalise that here."""
    from .tools import adhd_run
    ctx = kwargs.get("ctx")
    if ctx is None:
        # Some hosts pass ctx as a positional. Accept either shape.
        ctx = kwargs.get("agent") or kwargs.get("_ctx")
    if ctx is None:
        return _err("no ctx available; this tool can only run inside Hermes")
    # Apply config defaults to args before the handler runs them.
    merged = _apply_config_defaults(dict(args), ctx)
    return await adhd_run(merged, ctx=ctx, **kwargs)


def _err(msg: str) -> str:
    import json
    return json.dumps({"error": msg})


def register(ctx: Any) -> None:
    """Wire schemas → handlers, register the slash command and tool,
    and ship the bundled skill."""
    from . import schemas, commands

    # 1) Slash command: /adhd "<problem>" [flags]
    ctx.register_command(
        "adhd",
        handler=lambda raw: _adhd_command_handler(ctx, raw),
        description=(
            "ADHD — parallel divergent ideation under multiple cognitive "
            "frames (regulator, biology, speedrunner, 10-year-old, $0 "
            "budget, +10 more). Fans out isolated branches, scores, "
            "clusters, prunes traps, deepens survivors. Use on open-ended, "
            "high-stakes design / architecture / API / naming / fuzzy-"
            "debugging decisions. Skip for syntax, lookups, bugs with "
            "known root cause, or when the user asked for a 'standard' "
            "or 'quick' answer."
        ),
        args_hint=(
            '"<problem>" [--frames N] [--ideas N] [--top N] '
            "[--concurrency N] [--no-code-mode] [--no-anchor-strip] "
            "[--pack NAME] [--context PATH] [--json] [--quiet]"
        ),
    )

    # 2) Tool: adhd.run — for agents (and the LLM-as-tool flow).
    ctx.register_tool(
        name="adhd.run",
        toolset="adhd",
        schema=schemas.ADHD_RUN,
        handler=_adhd_run_tool_handler,
    )

    # 3) Bundled skill: copy of skills/adhd/SKILL.md.
    skill_dir = Path(__file__).parent / "skills"
    if skill_dir.is_dir():
        for child in sorted(skill_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                try:
                    ctx.register_skill(child.name, skill_md)
                except Exception:
                    logger.exception("could not register skill %s", child.name)