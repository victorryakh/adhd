"""LLM transport — replaces src/llm.ts (which wrapped the Claude Agent
SDK). On Hermes, all LLM traffic goes through `ctx.llm.complete` /
`ctx.llm.complete_structured`, so this module is just a thin wrapper
that:

- centralises the strip-fences / first-{or-[ parse that the original
  TypeScript did before validating against Zod;
- exposes two call shapes (free-form completion and structured
  completion) so callers don't need to know which ctx.llm method to
  pick for which phase.

The plugin's engine.py builds the right `messages` (or `instructions`
+ `input`) for each call; the `llm` interface here lets the engine
treat diverge / score / cluster / deepen uniformly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .types_mod import RunEvent


@dataclass
class LLMResult:
    text: str
    raw: Any  # the full PluginLlmCompleteResult / PluginLlmStructuredResult


# A thin callable so engine.py stays unit-testable: tests can swap
# out `_call_llm` for a stub that returns a canned string.
CallLLM = Callable[[str, str, Optional[str]], Awaitable[str]]


async def default_complete(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str],
    *,
    ctx: Any,
) -> str:
    """Call the host LLM through ctx.llm.complete with a system +
    user message pair. The `model=` override is gated by Hermes —
    pass-through is fine; PluginLlmTrustError is the host's problem."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict[str, Any] = {
        "messages": messages,
        "temperature": 0.7,
        "purpose": "adhd.phase",
    }
    if model is not None:
        kwargs["model"] = model
    result = await ctx.llm.acomplete(**kwargs)
    return result.text


def parse_json(raw: str) -> Any:
    """Strip ```json fences and parse. LLMs love to wrap. Find the
    first { or [ when there's a preamble. Mirrors parseJSON() in
    src/llm.ts minus the Zod step (validation is done by Hermes
    via json_schema on complete_structured)."""
    s = raw.strip()
    fence = _extract_fence(s)
    if fence is not None:
        s = fence.strip()
    first_obj = s.find("{")
    first_arr = s.find("[")
    if first_obj == -1:
        start = first_arr
    elif first_arr == -1:
        start = first_obj
    else:
        start = min(first_obj, first_arr)
    if start > 0:
        s = s[start:]
    return json.loads(s)


def _extract_fence(s: str) -> Optional[str]:
    """Return the contents of a ```json ... ``` fence, or None."""
    # Hand-rolled to avoid the regex module being subtly wrong on
    # nested backticks (the TS version used a non-greedy match).
    if not s.startswith("```"):
        return None
    lines = s.split("\n")
    if not lines:
        return None
    # First line is the fence opener (``` or ```json)
    # Find the closing fence.
    closing = None
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip().startswith("```"):
            closing = i
            break
    if closing is None or closing <= 1:
        return None
    return "\n".join(lines[1:closing])