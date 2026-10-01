"""JSON serialiser — converts RunResult into a JSON-friendly dict so
the tool handler can return a JSON string. Mirrors the implicit shape
the TypeScript code returned when callers used --json."""

from __future__ import annotations

from typing import Any, Dict, List

from .types_mod import Cluster, DeepenedIdea, Idea, RunResult, Score


def _idea_to_dict(i: Idea) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "id": i.id,
        "frameId": i.frame_id,
        "text": i.text,
        "depth": i.depth,
    }
    if i.rationale is not None:
        d["rationale"] = i.rationale
    if i.parent_id is not None:
        d["parentId"] = i.parent_id
    if i.cluster is not None:
        d["cluster"] = i.cluster
    if i.score is not None:
        d["score"] = _score_to_dict(i.score)
    return d


def _score_to_dict(s: Score) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "novelty": s.novelty,
        "viability": s.viability,
        "fit": s.fit,
        "total": s.total,
    }
    if s.trap is not None:
        d["trap"] = s.trap
    if s.strength is not None:
        d["strength"] = s.strength
    return d


def _cluster_to_dict(c: Cluster) -> Dict[str, Any]:
    return {"label": c.label, "ideaIds": c.idea_ids}


def _deepened_to_dict(d: DeepenedIdea) -> Dict[str, Any]:
    return {
        "ideaId": d.idea_id,
        "sketch": d.sketch,
        "childIdeas": [_idea_to_dict(c) for c in d.child_ideas],
    }


def result_to_dict(r: RunResult) -> Dict[str, Any]:
    return {
        "problem": r.problem,
        "reframe": r.reframe,
        "branches": [
            {"frameId": b.frame_id, "ideas": [_idea_to_dict(i) for i in b.ideas]}
            for b in r.branches
        ],
        "clusters": [_cluster_to_dict(c) for c in r.clusters],
        "shortlist": [_idea_to_dict(i) for i in r.shortlist],
        "nonObviousPick": (
            _idea_to_dict(r.non_obvious_pick) if r.non_obvious_pick is not None else None
        ),
        "traps": [_idea_to_dict(i) for i in r.traps],
        "deepened": [_deepened_to_dict(d) for d in r.deepened],
        "provocation": r.provocation,
    }