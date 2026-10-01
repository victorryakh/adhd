"""Tree-of-thought engine with pruning — 1:1 port of src/engine.ts.

The loop:
    1. Diverge wide — fan out N parallel branches, each running under a
       different cognitive frame. No critic, no cross-talk.
    2. Score every leaf on novelty / viability / fit.
    3. Cluster — surface the SHAPE of the idea space, not just the leaves.
    4. Prune to top-K and DEEPEN those by recursive expansion.
    5. Pick the non-obvious-but-viable one. Flag traps. Provoke once.

Convergence happens after divergence, never during.

The TypeScript original used `p-limit` for concurrency control and Zod
for runtime JSON validation. Both are replaced here:
- `asyncio.Semaphore` does what `p-limit` did.
- `ctx.llm.complete_structured(json_schema=...)` lets Hermes do the
  validation. We still have a fallback parse path for when the host
  fails to extract JSON from a wrapped response.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from .frames import select_frames
from .llm import parse_json
from .types_mod import (
    Branch,
    Cluster,
    ClusterDone,
    DeepenDone,
    DeepenStart,
    DeepenedIdea,
    FrameDone,
    FrameStart,
    Idea,
    ReframeDone,
    RunEvent,
    RunOptions,
    RunResult,
    Score,
    ScoreDone,
    Warn,
)


# JSON schemas for complete_structured. Mirrors the Zod schemas in
# src/engine.ts (DivergeRowSchema, ScoreRowSchema, ClusterSchema,
# DeepenSchema, ReframeSchema) — kept as plain dicts so the host can
# validate without us importing jsonschema.
DIVERGE_ROW_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": ["text"],
    },
}

SCORE_ROW_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "novelty": {"type": "number", "minimum": 0, "maximum": 10},
            "viability": {"type": "number", "minimum": 0, "maximum": 10},
            "fit": {"type": "number", "minimum": 0, "maximum": 10},
            "trap": {"type": "string"},
            "strength": {"type": "string"},
        },
        "required": ["id", "novelty", "viability", "fit"],
    },
}

CLUSTER_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "ideaIds": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["label", "ideaIds"],
    },
}

DEEPEN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "sketch": {"type": "string"},
        "childIdeas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    "required": ["sketch", "childIdeas"],
}

REFRAME_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reframed": {"type": "string"},
        "changed": {"type": "boolean"},
        "note": {"type": "string"},
    },
    "required": ["reframed", "changed"],
}


# System prompts — verbatim from src/engine.ts.
DIVERGE_SYSTEM = """You are in DIVERGENT mode. You are a generator, not a critic.
Rules:
- Output a JSON array only. No prose before/after.
- Generate the requested number of distinct ideas.
- Each idea is a SHORT phrase or single sentence. No paragraphs.
- Push past the obvious. The first 3 ideas you'd think of are banned —
  assume the reader already had those. Aim for the awkward middle.
- Bad, weird, and absurd ideas are welcome; they seed better ones.
- Do not evaluate, hedge, or rank. Just generate."""

SCORE_SYSTEM = """You are in CONVERGENT mode. You are now the critic.
Score each idea on three axes 0-10:
- novelty: distance from the obvious default solution
- viability: could this actually ship / work in practice
- fit: how directly it addresses the stated problem

Tell the truth about weaknesses — don't soften the substance. But the
critic's job is to produce two symmetric signals, not just one:

- "strength": required for every idea, even weak ones. The single most
  concrete thing this idea gets right that a competing idea doesn't.
- "trap" (optional): if the idea looks attractive but has a hidden cost
  (false economy, won't scale, premature abstraction), name it as a
  specific, actionable heads-up — e.g. "solid for a prototype, breaks
  past 10k concurrent users" — not a dismissal like "bad idea." The
  fact stays the fact; only the framing changes: information you can
  act on, not a verdict on the idea's worth.

Output JSON only."""

CLUSTER_SYSTEM = """You group ideas into 3-6 clusters by their UNDERLYING ANGLE
(not by surface keywords). Cluster labels name the angle, e.g.
"remove-the-server plays", "push-work-to-client plays", "cache-shaped plays".
Output JSON only."""

REFRAME_SYSTEM = """You strip load-bearing anchors from a problem statement before divergent
brainstorming. An anchor is an incidental implementation detail (a specific
tech stack, an existing tool name, the current architecture) that isn't a
real constraint but silently narrows every downstream idea to variations on
what's already there.

Rules:
- Keep anchors that are genuine immutable constraints: compliance/legal
  requirements, hard budget or time limits, physical/protocol constraints,
  anything the user would reject an answer for violating.
- Strip anchors that are just "how it happens to be built today" — current
  database, current framework, current team structure — UNLESS removing
  them would make the problem meaningless or invite disallowed options.
- If you strip something, restate the problem as the underlying
  job-to-be-done, not the current implementation.
- If nothing needs stripping, return the problem unchanged and set
  "changed" to false.
Output JSON only: {"reframed": "...", "changed": true|false, "note": "one clause on what was stripped, omit if unchanged"}"""

DEEPEN_SYSTEM = """You are in FOCUS mode. Take one promising idea and connect dots:
- Sketch how it would actually work (4-8 sentences).
- Name the load-bearing risk.
- Name the first concrete step a coder would take.
- Then generate 3-5 sub-ideas that branch off this one (variations,
  combinations with other domains, things this unlocks).
Output JSON only."""


# --- per-phase functions ---


async def _call_structured(
    ctx: Any,
    system_prompt: str,
    instructions: str,
    schema: Dict[str, Any],
    *,
    model: Optional[str] = None,
) -> Optional[Any]:
    """Issue a complete_structured call. Returns parsed dict/list, or
    None on parse failure. Hermes handles validation; we still fall
    back to parse_json() if the host couldn't extract a clean
    JSON payload."""
    input_blocks = [{"type": "text", "text": instructions}]
    kwargs: Dict[str, Any] = {
        "system_prompt": system_prompt,
        "instructions": instructions,
        "input": input_blocks,
        "json_schema": schema,
        "temperature": 0.0,
        "purpose": "adhd.phase",
    }
    if model is not None:
        kwargs["model"] = model
    try:
        result = await ctx.llm.acomplete_structured(**kwargs)
    except Exception as e:
        return None
    if getattr(result, "parsed", None) is not None:
        return result.parsed
    text = getattr(result, "text", "") or ""
    if not text.strip():
        return None
    try:
        return parse_json(text)
    except Exception:
        return None


async def reframe_problem(
    ctx: Any,
    problem: str,
    context: Optional[str],
    model: Optional[str],
) -> Dict[str, Any]:
    """Strip incidental anchors from the problem before diverge.
    Fail-open: if anything goes wrong, fall back to the original
    problem with changed=False."""
    parts = [f"PROBLEM:\n{problem}\n"]
    if context:
        parts.append(f"\nCONTEXT:\n{context}\n")
    parts.append("\nStrip incidental anchors, keep real constraints. Output JSON only.")
    instructions = "".join(parts)

    parsed = await _call_structured(
        ctx, REFRAME_SYSTEM, instructions, REFRAME_SCHEMA, model=model,
    )
    if not isinstance(parsed, dict):
        return {"reframed": problem, "changed": False}
    reframed = (parsed.get("reframed") or "").strip()
    if not reframed or not parsed.get("changed", False):
        return {"reframed": problem, "changed": False}
    return {"reframed": reframed, "changed": True}


async def diverge_branch(
    ctx: Any,
    problem: str,
    context: Optional[str],
    frame: Any,
    ideas_per_frame: int,
    model: Optional[str],
) -> Branch:
    """Generate one frame's ideas. Each call is its own context —
    this is the isolation invariant."""
    parts = [f"PROBLEM:\n{problem}\n"]
    if context:
        parts.append(f"\nCONTEXT:\n{context}\n")
    parts.append(
        f"\nFRAME — {frame.label}:\n{frame.prompt}\n\n"
        f"Generate {ideas_per_frame} ideas under this frame.\n"
        'Output JSON array: [{"text": "...", "rationale": "..."}]\n'
        "- text: one phrase/sentence, the idea itself\n"
        "- rationale: 1 short clause on why this frame surfaces it (optional)"
    )
    instructions = "".join(parts)

    parsed = await _call_structured(
        ctx, DIVERGE_SYSTEM, instructions, DIVERGE_ROW_SCHEMA, model=model,
    )
    if not isinstance(parsed, list):
        return Branch(frame_id=frame.id, ideas=[])

    ideas: List[Idea] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        ideas.append(
            Idea(
                id=str(uuid.uuid4()),
                frame_id=frame.id,
                text=text,
                rationale=row.get("rationale"),
                depth=0,
            )
        )
    return Branch(frame_id=frame.id, ideas=ideas)


async def score_ideas(
    ctx: Any,
    problem: str,
    ideas: List[Idea],
    model: Optional[str],
) -> Dict[str, Score]:
    """Score each idea 0-10 on novelty / viability / fit. Viability
    is the gatekeeper — a brilliant unshippable idea is a trap."""
    if not ideas:
        return {}
    lines = "\n".join(f"{i.id} :: {i.text}" for i in ideas)
    instructions = (
        f"PROBLEM:\n{problem}\n\nIDEAS (id → text):\n{lines}\n\n"
        "Score each. Output JSON array:\n"
        '[{"id":"...","novelty":0-10,"viability":0-10,"fit":0-10,'
        '"strength":"...","trap":"... or omit"}]'
    )

    parsed = await _call_structured(
        ctx, SCORE_SYSTEM, instructions, SCORE_ROW_SCHEMA, model=model,
    )
    if not isinstance(parsed, list):
        return {}

    scores: Dict[str, Score] = {}
    for row in parsed:
        if not isinstance(row, dict):
            continue
        idea_id = row.get("id")
        if not idea_id:
            continue
        # Weight: novelty matters because the whole point is escaping
        # the obvious, but viability is the gatekeeper — a brilliant
        # unshippable idea is a trap.
        novelty = float(row.get("novelty") or 0)
        viability = float(row.get("viability") or 0)
        fit = float(row.get("fit") or 0)
        total = novelty * 0.35 + viability * 0.40 + fit * 0.25
        scores[idea_id] = Score(
            novelty=novelty,
            viability=viability,
            fit=fit,
            total=total,
            trap=row.get("trap"),
            strength=row.get("strength"),
        )
    return scores


async def cluster_ideas(
    ctx: Any,
    problem: str,
    ideas: List[Idea],
    model: Optional[str],
) -> List[Cluster]:
    """Group ideas by underlying angle. 3-6 clusters is the target."""
    if not ideas:
        return []
    lines = "\n".join(f"{i.id} :: {i.text}" for i in ideas)
    instructions = (
        f"PROBLEM:\n{problem}\n\nIDEAS:\n{lines}\n\n"
        'Output JSON: [{"label":"...","ideaIds":["...","..."]}]'
    )
    parsed = await _call_structured(
        ctx, CLUSTER_SYSTEM, instructions, CLUSTER_SCHEMA, model=model,
    )
    if not isinstance(parsed, list):
        return []

    clusters: List[Cluster] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        label = (row.get("label") or "").strip()
        if not label:
            continue
        idea_ids = [str(x) for x in (row.get("ideaIds") or [])]
        clusters.append(Cluster(label=label, idea_ids=idea_ids))
    return clusters


async def deepen_idea(
    ctx: Any,
    problem: str,
    idea: Idea,
    siblings: List[Idea],
    model: Optional[str],
) -> DeepenedIdea:
    """Connect dots on one promising idea: sketch + child ideas."""
    sibling_lines = "\n".join(
        f"- {s.text}"
        for s in siblings
        if s.id != idea.id
    )[:12]
    instructions = (
        f"PROBLEM:\n{problem}\n\nFOCUS IDEA:\n{idea.text}"
        + (f"\n({idea.rationale})" if idea.rationale else "")
        + f"\n\nSIBLING IDEAS (use for recombination if useful):\n{sibling_lines}\n\n"
        "Output JSON:\n"
        "{\n"
        '  "sketch": "4-8 sentences. How it works. Load-bearing risk. First concrete step.",\n'
        '  "childIdeas": [\n'
        '    {"text": "...", "rationale": "variation / hybrid / unlock"}\n'
        "  ]\n"
        "}"
    )
    parsed = await _call_structured(
        ctx, DEEPEN_SYSTEM, instructions, DEEPEN_SCHEMA, model=model,
    )
    if not isinstance(parsed, dict):
        return DeepenedIdea(idea_id=idea.id, sketch="(deepen pass failed to parse)", child_ideas=[])

    sketch = (parsed.get("sketch") or "").strip() or "(empty sketch)"
    child_ideas: List[Idea] = []
    for c in parsed.get("childIdeas") or []:
        if not isinstance(c, dict):
            continue
        text = (c.get("text") or "").strip()
        if not text:
            continue
        child_ideas.append(
            Idea(
                id=str(uuid.uuid4()),
                frame_id=idea.frame_id,
                text=text,
                rationale=c.get("rationale"),
                depth=idea.depth + 1,
                parent_id=idea.id,
            )
        )
    return DeepenedIdea(idea_id=idea.id, sketch=sketch, child_ideas=child_ideas)


# --- main orchestrator ---


async def run(ctx: Any, opts: RunOptions) -> RunResult:
    """The four-phase orchestrator. Identical semantics to src/engine.ts::run."""

    problem = opts.problem
    context = opts.context
    frames_per_run = opts.frames_per_run if opts.frames_per_run is not None else 5
    ideas_per_frame = opts.ideas_per_frame if opts.ideas_per_frame is not None else 6
    top_k = opts.top_k if opts.top_k is not None else 3
    concurrency = opts.concurrency if opts.concurrency is not None else 4
    code_mode = opts.code_mode if opts.code_mode is not None else True
    strip_anchors = opts.strip_anchors if opts.strip_anchors is not None else True
    model = opts.model
    critic_model = opts.critic_model or model
    packs = opts.packs if opts.packs else ["core"]
    on_event = opts.on_event

    # The critic (score + cluster) can run on a different model from
    # the generator to decorrelate errors. Defaults to the generator
    # model.
    critic = critic_model

    def _emit(ev: RunEvent) -> None:
        if on_event is not None:
            try:
                on_event(ev)
            except Exception:
                pass

    # Frame selection happens BEFORE the reframe so an unknown pack
    # fails fast, before any LLM call.
    frames = select_frames(frames_per_run, code_mode, packs)

    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(coro):
        async with semaphore:
            return await coro

    # PHASE 0 — REFRAME. Strip incidental anchors (current stack,
    # existing tool names) from the problem statement before it ever
    # reaches a branch. Every branch otherwise sees the same raw
    # problem, so an anchor buried in it infects all N branches
    # regardless of branch isolation. Real constraints (compliance,
    # budget, physical limits) are preserved. Convergence
    # (score/cluster/deepen) still judges against the ORIGINAL
    # problem — an idea has to fit the real constraints to be viable.
    diverge_problem = problem
    reframe_text: Optional[str] = None
    if strip_anchors:
        r = await reframe_problem(ctx, problem, context, model)
        if r.get("changed") and (r.get("reframed") or "").strip():
            diverge_problem = r["reframed"]
            reframe_text = r["reframed"]
        _emit(ReframeDone(changed=bool(reframe_text)))

    # PHASE 1 — DIVERGE. Pure parallel fan-out. No branch sees another.
    async def _one_diverge(f):
        _emit(FrameStart(frame_id=f.id, frame_label=f.label))
        b = await diverge_branch(ctx, diverge_problem, context, f, ideas_per_frame, model)
        _emit(FrameDone(frame_id=f.id, count=len(b.ideas)))
        return b

    branches: List[Branch] = await asyncio.gather(
        *[_bounded(_one_diverge(f)) for f in frames]
    )
    all_ideas: List[Idea] = [i for b in branches for i in b.ideas]

    # PHASE 2 — SCORE + CLUSTER. Critic comes back online.
    score_map, clusters = await asyncio.gather(
        score_ideas(ctx, problem, all_ideas, critic),
        cluster_ideas(ctx, problem, all_ideas, critic),
    )
    for i in all_ideas:
        i.score = score_map.get(i.id)
    for c in clusters:
        for idea_id in c.idea_ids:
            idea = next((x for x in all_ideas if x.id == idea_id), None)
            if idea is not None:
                idea.cluster = c.label
    _emit(ScoreDone(total=len(all_ideas)))
    _emit(ClusterDone(clusters=len(clusters)))

    # Shortlist: top by total, excluding traps. Traps reported separately.
    def _sc(i: Idea) -> Score:
        assert i.score is not None
        return i.score

    traps: List[Idea] = [i for i in all_ideas if i.score is not None and i.score.trap]
    ranked = sorted(
        [i for i in all_ideas if i.score is not None and not i.score.trap],
        key=lambda x: _sc(x).total,
        reverse=True,
    )
    shortlist = ranked[: max(2, min(4, top_k + 1))]

    # Non-obvious pick = highest novelty among the viable shortlist.
    if shortlist:
        non_obvious_pick = max(
            shortlist,
            key=lambda x: _sc(x).novelty + _sc(x).viability * 0.5,
        )
    else:
        non_obvious_pick = None

    # PHASE 3 — FOCUS / DEEPEN top-K. This is the "connecting the dots" pass.
    to_deepen = ranked[:top_k]

    async def _one_deepen(idea):
        _emit(DeepenStart(idea_id=idea.id, text=idea.text))
        d = await deepen_idea(ctx, problem, idea, all_ideas, model)
        _emit(DeepenDone(idea_id=idea.id))
        return d

    deepened: List[DeepenedIdea] = await asyncio.gather(
        *[_bounded(_one_deepen(i)) for i in to_deepen]
    )

    # One provocation = a wild-tagged frame's lowest-scoring-but-
    # highest-novelty leaf, reframed as a question. Cheap, doesn't
    # need another LLM call.
    wildcard: Optional[Idea] = None
    candidates: List[Idea] = [i for i in all_ideas if i.score is not None]
    if candidates:
        wildcard = max(candidates, key=lambda x: _sc(x).novelty)
    if wildcard is not None:
        provocation = f"What if we took this seriously: {wildcard.text}"
    else:
        provocation = "What's the assumption nobody named yet?"

    return RunResult(
        problem=problem,
        reframe=reframe_text,
        branches=branches,
        clusters=clusters,
        shortlist=shortlist,
        non_obvious_pick=non_obvious_pick,
        traps=traps,
        deepened=deepened,
        provocation=provocation,
    )