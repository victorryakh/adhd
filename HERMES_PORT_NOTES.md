# Hermes Agent — ADHD Port Notes

This branch (`hermes-agent-adaptation`) is the upstream fork of `UditAkhourii/adhd`
prepared for porting the project into a Hermes Agent plugin.

## Status: SCAFFOLD ONLY

The porting work itself is tracked by sibling task `t_f8f684a4` (implementation) and
informed by `analysis.md` from the parent study task `t_8a800838`.

## High-level porting plan (from analysis.md)

- Replace TypeScript source under `src/` with a Python `hermes_agent` plugin.
- Map `src/engine.ts` (4-phase run-loop) → plugin command handler.
- Map `src/llm.ts` (Anthropic-SDK wrapper) → `ctx.llm.complete` / `ctx.llm.complete_structured`.
- Map `src/frames.ts` + `src/packs/core.ts` (frame catalog) → bundled assets.
- Map `src/types.ts` / Zod schemas → Pydantic models → `model_json_schema()` dicts.
- Replace `p-limit` with `asyncio.Semaphore` + `asyncio.gather`.
- Drop `@anthropic-ai/claude-agent-sdk`, `tsx`, `typescript` — host-owned credentials via Hermes.
- Add `plugin.yaml` declaring `llm.model_override` capability (for critic-model override).
- Add `pyproject.toml` with `hermes_agent.plugins` entry-point.
- Register via `ctx.register_command("adhd", handler=..., description=..., args_hint=...)`,
  optionally `ctx.register_tool("adhd.run", toolset=..., schema=..., handler=...)`,
  and bundle the original `skills/adhd/SKILL.md` via `ctx.register_skill("adhd", ...)`.
- Score weights (0.35 / 0.40 / 0.25) — to be reviewed; possibly moved to `config_schema`.

## Hotspots to preserve

- `divergeBranch` — branch isolation must not leak across `ctx.llm` calls.
- `reframeProblem` — REFRAME_SYSTEM is ambiguous; do NOT silently fail-open on parse errors.
- `scoreIdeas` — score weights currently hardcoded; decide keep-as-is vs. config_schema.

## Open questions for the implementer

- How to bundle the original 15 frame system-prompts (one file? one folder? as Python module?).
- Whether `frames_per_run / ideas_per_frame / top_k / concurrency / code_mode / strip_anchors`
  become Hermes plugin config-schema entries (most likely yes).
- Whether `--context` CLI flag becomes a slash-command argument or a `register_tool` schema arg.

---

Populated by the adaptator. Keep this file as the single source of truth for
port-time rationale; mirror to `README.md` only once the plugin ships.