"""Tool handlers — what runs when the LLM calls adhd.run."""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from . import engine
from .serialize import result_to_dict
from .types_mod import RunOptions


logger = logging.getLogger(__name__)


def _coerce_str_list(v: Any) -> Optional[List[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        return [v]
    return None


async def adhd_run(args: dict, **kwargs) -> str:
    """Handler for `adhd.run`. Receives the LLM's arguments, runs the
    four-phase loop, and returns a JSON string. Always returns JSON —
    success and error alike. Accepts **kwargs for forward
    compatibility with the host injecting context fields."""
    problem = (args.get("problem") or "").strip()
    if not problem:
        return json.dumps({
            "error": "missing required argument 'problem'",
            "hint": "pass a one- or two-sentence problem statement",
        })

    # Cast dict.get() values to the Optional types RunOptions declares.
    # Pyright can't narrow dict.get() return types to declared Optionals,
    # but at runtime these are accepted because every field is Optional.
    int_fields = ("frames_per_run", "ideas_per_frame", "top_k", "concurrency")
    bool_fields = ("code_mode", "strip_anchors")
    opt_kwargs: dict[str, Any] = {"problem": problem, "context": args.get("context")}
    for k in int_fields:
        v = args.get(k)
        if v is not None:
            opt_kwargs[k] = int(v)
    for k in bool_fields:
        v = args.get(k)
        if v is not None:
            opt_kwargs[k] = bool(v)
    for k in ("model", "critic_model"):
        v = args.get(k)
        if v is not None:
            opt_kwargs[k] = v
    packs = _coerce_str_list(args.get("packs"))
    if packs is not None:
        opt_kwargs["packs"] = packs

    try:
        opts = RunOptions(**opt_kwargs)
    except Exception as e:
        return json.dumps({"error": f"invalid arguments: {e}"})

    # The host injects a context object as a keyword (e.g. ctx).
    # Pull it out of kwargs so RunOptions doesn't get a stray field.
    ctx = kwargs.get("ctx")
    if ctx is None:
        return json.dumps({
            "error": "no ctx available; this tool can only run inside Hermes",
        })

    try:
        result = await engine.run(ctx, opts)
    except Exception as e:
        logger.exception("adhd.run failed")
        return json.dumps({"error": f"run failed: {e}"})

    return json.dumps(result_to_dict(result))