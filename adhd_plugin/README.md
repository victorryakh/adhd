# ADHD — Hermes Agent Plugin

> Parallel divergent ideation for coding agents. Fans out N isolated
> branches under different cognitive frames (regulator, biology,
> speedrunner, 10-year-old, $0 budget, +10 more), scores them on
> novelty / viability / fit, clusters by underlying angle, prunes
> traps, and deepens the survivors. Tree-of-thought with pruning.

This repository hosts the **upstream `UditAkhourii/adhd`** (Node/TS,
built on the Claude Agent SDK) and a **Hermes Agent adaptation** in
`adhd_plugin/`. The adaptation:

- runs the same four-phase loop as the original (diverge → score +
  cluster → deepen → provoke)
- routes all LLM traffic through `ctx.llm.acomplete` /
  `ctx.llm.acomplete_structured` (no SDK, no API keys, no direct
  HTTP)
- registers a `/adhd` slash command, an `adhd.run` tool, and a
  bundled `adhd` skill on the same name
- ships a tiny pytest-free test suite under
  `adhd_plugin/tests/run_all.py`

## Install

```
hermes plugins install victorryakh/adhd
```

Then in any session (CLI, gateway):

```
/adhd "design a retry strategy for a CLI whose LLM hangs for 90s"
```

The plugin auto-registers at startup; no `hermes plugins enable` step
required. To uninstall:

```
hermes plugins remove adhd
```

## Slash command

```
/adhd "<problem>" [flags]
```

Flags mirror the original CLI:

| Flag | Meaning | Default |
|---|---|---|
| `--frames N` | frames per run | 5 |
| `--ideas N` | ideas per frame | 6 |
| `--top N` | ideas to deepen | 3 |
| `--concurrency N` | max parallel LLM calls | 4 |
| `--no-code-mode` | bias toward non-engineering frames | code_mode=true |
| `--no-anchor-strip` | keep incidental anchors | strip_anchors=true |
| `--pack NAME` | repeatable; pack to draw frames from | core |
| `--context PATH` | read context from a file (max 10 MB) | — |
| `--context-stdin` | read context from stdin | — |
| `--json` | emit JSON instead of rendered text | rendered |
| `--quiet` | trim wide-set / traps blocks | full |
| `--help` | print help | — |

Default values can be overridden at the operator level under
`plugins.entries.adhd.settings.*` (see `plugin.yaml::config_schema`).

## Tool

`adhd.run` is the tool equivalent. The model can call it directly
when an open-ended, high-stakes decision appears in the conversation
flow — it's the same loop, but invoked from the agent rather than
the user. Returns a JSON `RunResult` with `branches`, `clusters`,
`shortlist`, `nonObviousPick`, `traps`, `deepened`, `provocation`.

The tool description is in `adhd_plugin/schemas.py::ADHD_RUN` —
that's what the LLM reads to decide when to call it.

## Skill

A bundled `adhd` skill ships under
`adhd_plugin/skills/adhd/SKILL.md`. Same content as the upstream
Claude Code skill, with a small footer pointing users at the plugin
for the Hermes case. Load with `skill_view("adhd:adhd")`.

## Configuration

`plugin.yaml` declares a `config_schema` so operators can override
defaults without code changes:

```yaml
plugins:
  entries:
    adhd:
      llm:
        allow_model_override: true   # gated by capability
        allowed_models: ["anthropic/claude-3-5-sonnet", "openai/gpt-4o-mini"]
      settings:
        frames_per_run: 7
        ideas_per_frame: 8
        top_k: 4
        concurrency: 6
        code_mode: false
        strip_anchors: true
        default_pack: core
```

`llm.model_override` is a capability declared by the plugin; consent is
asked once at install / enable time. Without consent, `model=` and
`critic_model=` arguments raise `PluginLlmTrustError` from the host.

## Tests

Hermes plugin tests are zero-dependency — no pytest required:

```bash
cd adhd_plugin
python -m adhd_plugin.tests.run_all
```

Or from the repo root:

```bash
python3.11 -m adhd_plugin.tests.run_all
```

Tests cover:

- frame selection (mirrors upstream `tests/frames.test.ts`)
- JSON parsing (`parse_json`, including fence stripping and preamble
  detection)
- renderer output shape (mirrors upstream `tests/cli.test.ts`
  behaviour)
- slash-command argument parsing

The engine itself is hard to test without a real `ctx.llm`, so the
golden-path logic is exercised through end-to-end smoke checks at
install time (Hermes runs `register()` and surfaces failures via
`hermes plugins list`).

## Layout

```
adhd_plugin/
├── plugin.yaml          manifest (name, version, capabilities, schema)
├── pyproject.toml       pip-installable metadata (entry points)
├── __init__.py          register(ctx) wires everything up
├── types_mod.py         data classes (Frame, Idea, Score, RunResult, ...)
├── frames.py            selectFrames() — same logic as upstream
├── packs/core.py        15 core frames copied verbatim
├── llm.py               parse_json + complete() / complete_structured()
├── engine.py            the four-phase orchestrator
├── render.py            ANSI terminal renderer
├── serialize.py         RunResult → JSON dict for tools / --json
├── schemas.py           tool schema (LLM-facing)
├── tools.py             adhd.run handler
├── commands.py          /adhd slash-command handler
└── tests/
    ├── __init__.py
    ├── run_all.py       zero-dep test runner
    ├── test_frames.py
    ├── test_llm.py
    ├── test_render.py
    └── test_command_parse.py
```

`src/`, `tests/`, `skills/`, `bench/`, `.claude-plugin/` are the
**upstream Node/TS implementation** — kept in place for reference. The
Hermes plugin is fully under `adhd_plugin/`.

## Provenance

This is `victorryakh/adhd`, forked from `UditAkhourii/adhd`. The
Hermes plugin is a clean-room reimplementation of the public API
(types, frames, engine, render, skill) using Hermes's
`ctx.llm` contract instead of the Claude Agent SDK. All 15 frames,
the four-phase loop, the score weights (0.35 / 0.40 / 0.25), the
shortlist / non-obvious-pick / traps / provocation output shape, and
the bundled skill text are preserved.

## License

MIT (inherited from upstream).