"""Slash command handler — implements /adhd.

Mirrors the CLI from src/cli.ts but as an in-session command: takes a
raw argument string, parses minimal flags (so the user gets parity
with the original CLI), runs the engine, and returns either the
rendered ANSI output or JSON.
"""

from __future__ import annotations

import logging
import shlex
from typing import Any, List, Optional

from . import engine, render
from .serialize import result_to_dict
from .types_mod import RunOptions


logger = logging.getLogger(__name__)


HELP = """\
/adhd — parallel divergent ideation under cognitive frames.

Usage: /adhd "<problem>" [flags]

Flags:
  --frames N              frames per run (default 5)
  --ideas N               ideas per frame (default 6)
  --top N                 top-K to deepen (default 3)
  --concurrency N         max parallel LLM calls (default 4)
  --no-code-mode          bias toward non-engineering frames
  --no-anchor-strip       keep incidental anchors in the problem
  --pack NAME             repeatable; default is 'core'
  --context PATH          read context from a file (max 10 MB)
  --context-stdin         read context from stdin
  --json                  emit the RunResult as JSON instead of rendered
  --quiet                  omit the wide set / traps section
  --help                  print this help
"""


def _read_context(path: str) -> Optional[str]:
    """Mirrors src/cli.ts --context: stat, refuse > 10 MB, then read."""
    import os
    try:
        size = os.stat(path).st_size
    except OSError as e:
        raise ValueError(f"can't stat --context file {path}: {e}")
    if size > 10 * 1024 * 1024:
        raise ValueError(f"--context file {path} is larger than 10 MB")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_args(raw_args: str) -> dict:
    """Tiny flag parser — supports quoted problem string, repeatable
    --pack, --json / --quiet, --context / --context-stdin."""
    if raw_args is None:
        raw_args = ""
    raw_args = raw_args.strip()
    if not raw_args:
        return {"_error": "no problem provided", "_help": HELP}

    if raw_args == "--help" or raw_args == "-h":
        return {"_help": HELP}

    try:
        tokens = shlex.split(raw_args)
    except ValueError as e:
        return {"_error": f"argument parse failed: {e}", "_help": HELP}

    # The first non-flag token is the problem. Everything else is
    # flags. We don't try to be clever — quoted strings carry the
    # whole problem; newlines in the user input become spaces after
    # shlex.
    problem_parts: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--") or tok.startswith("-"):
            break
        problem_parts.append(tok)
        i += 1
    if not problem_parts:
        return {"_error": "no problem provided", "_help": HELP}
    problem = " ".join(problem_parts)

    flags = {
        "frames_per_run": None,
        "ideas_per_frame": None,
        "top_k": None,
        "concurrency": None,
        "code_mode": True,
        "strip_anchors": True,
        "packs": None,
        "context": None,
        "json": False,
        "quiet": False,
    }

    while i < len(tokens):
        tok = tokens[i]
        if tok == "--frames":
            i += 1
            if i >= len(tokens):
                return {"_error": "--frames needs a number", "_help": HELP}
            flags["frames_per_run"] = int(tokens[i])
        elif tok == "--ideas":
            i += 1
            flags["ideas_per_frame"] = int(tokens[i])
        elif tok == "--top":
            i += 1
            flags["top_k"] = int(tokens[i])
        elif tok == "--concurrency":
            i += 1
            flags["concurrency"] = int(tokens[i])
        elif tok == "--no-code-mode":
            flags["code_mode"] = False
        elif tok == "--no-anchor-strip":
            flags["strip_anchors"] = False
        elif tok == "--pack":
            i += 1
            if i >= len(tokens):
                return {"_error": "--pack needs a name", "_help": HELP}
            flags["packs"] = (flags["packs"] or []) + [tokens[i]]
        elif tok == "--context":
            i += 1
            if i >= len(tokens):
                return {"_error": "--context needs a path", "_help": HELP}
            try:
                flags["context"] = _read_context(tokens[i])
            except ValueError as e:
                return {"_error": str(e), "_help": HELP}
        elif tok == "--context-stdin":
            flags["context"] = __import__("sys").stdin.read()
        elif tok == "--json":
            flags["json"] = True
        elif tok == "--quiet":
            flags["quiet"] = True
        elif tok == "--help" or tok == "-h":
            return {"_help": HELP}
        else:
            return {"_error": f"unknown flag: {tok}", "_help": HELP}
        i += 1

    flags["problem"] = problem
    return flags


async def handle_adhd(ctx: Any, raw_args: str) -> str:
    parsed = _parse_args(raw_args)
    if "_help" in parsed and "_error" not in parsed and len(parsed) == 1:
        return parsed["_help"]
    if "_error" in parsed:
        msg = parsed["_error"]
        help_text = parsed.get("_help", "")
        return f"{msg}\n\n{help_text}"

    problem = parsed["problem"]

    int_fields = ("frames_per_run", "ideas_per_frame", "top_k", "concurrency")
    bool_fields = ("code_mode", "strip_anchors")
    opt_kwargs: dict[str, Any] = {"problem": problem, "context": parsed.get("context")}
    for k in int_fields:
        v = parsed.get(k)
        if v is not None:
            opt_kwargs[k] = int(v)
    for k in bool_fields:
        v = parsed.get(k)
        if v is not None:
            opt_kwargs[k] = bool(v)
    packs = parsed.get("packs")
    if packs is not None:
        opt_kwargs["packs"] = list(packs)

    try:
        opts = RunOptions(**opt_kwargs)
    except Exception as e:
        return f"invalid arguments: {e}\n\n{HELP}"

    try:
        result = await engine.run(ctx, opts)
    except Exception as e:
        logger.exception("/adhd run failed")
        return f"run failed: {e}"

    if parsed.get("json"):
        import json
        return json.dumps(result_to_dict(result), indent=2)

    text = render.render_text(result)
    if parsed.get("quiet"):
        # Trim the wide-set and traps blocks (the "skimmable only" view).
        lines = text.split("\n")
        keep = []
        in_section = None
        for line in lines:
            if line.startswith("Wide set"):
                in_section = "wide"
                continue
            if line.startswith("Traps"):
                in_section = "traps"
                continue
            if line.startswith("Converge") or line.startswith("Focus") or line.startswith("Provocation"):
                in_section = None
            if in_section in ("wide", "traps"):
                continue
            keep.append(line)
        text = "\n".join(keep)
    return text