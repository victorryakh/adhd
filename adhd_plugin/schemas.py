"""Tool schemas — JSON-shape descriptions the LLM reads to decide
when to call the tool and how to shape its arguments."""

from __future__ import annotations

from typing import Any, Dict


ADHD_RUN: Dict[str, Any] = {
    "name": "adhd.run",
    "description": (
        "Run ADHD — parallel divergent ideation under multiple cognitive "
        "frames (regulator, biology, speedrunner, 10-year-old, $0 budget, "
        "and 10 more). Fans out isolated branches, scores on novelty / "
        "viability / fit, clusters by underlying angle, prunes traps, and "
        "deepens the survivors. Returns a structured RunResult with "
        "branches, shortlist, non-obvious pick, traps, deepened sketches, "
        "and one provocation. Use on open-ended, high-stakes design / "
        "architecture / API / naming / fuzzy-debugging decisions. Do NOT "
        "use for syntax, lookups, bugs with known root cause, or when the "
        "user asked for a 'standard' or 'quick' answer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "problem": {
                "type": "string",
                "description": (
                    "The problem to brainstorm against. One to two "
                    "sentences. Real constraints (compliance, budget, "
                    "physical limits) should stay; incidental anchors "
                    "(current stack, existing tool names) are stripped "
                    "by default before fan-out."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional codebase snippets, stack details, or "
                    "constraints to ground the ideation."
                ),
            },
            "frames_per_run": {
                "type": "integer",
                "description": (
                    "How many cognitive frames to fan out (default 5, "
                    "min 2, max 10). More frames = broader divergence, "
                    "more LLM calls."
                ),
            },
            "ideas_per_frame": {
                "type": "integer",
                "description": "Ideas generated per frame (default 6).",
            },
            "top_k": {
                "type": "integer",
                "description": "How many top ideas to deepen (default 3).",
            },
            "concurrency": {
                "type": "integer",
                "description": "Maximum parallel LLM calls (default 4).",
            },
            "code_mode": {
                "type": "boolean",
                "description": (
                    "Bias frame selection toward engineering / design "
                    "frames (default true)."
                ),
            },
            "strip_anchors": {
                "type": "boolean",
                "description": (
                    "Strip incidental anchors from the problem before "
                    "diverge (default true)."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    "Optional model override for generator calls. "
                    "Gated by the operator; only fill if your call needs "
                    "a specific model."
                ),
            },
            "critic_model": {
                "type": "string",
                "description": (
                    "Optional model override for the critic passes "
                    "(score + cluster). Use a different family from the "
                    "generator to decorrelate critic errors."
                ),
            },
            "packs": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Frame pack names to draw from (default ['core']). "
                    "Unknown packs cause the run to fail before any LLM "
                    "call."
                ),
            },
        },
        "required": ["problem"],
    },
}