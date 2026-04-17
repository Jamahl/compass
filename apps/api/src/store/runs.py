"""In-memory run store. Single-process only. Lost on restart — by design for MVP."""

from __future__ import annotations

from typing import Any

from ..models import ArtifactMeta, RunRequest, RunState, Stage

runs: dict[str, RunState] = {}


def create_run(run_id: str, request: RunRequest) -> RunState:
    state = RunState(
        run_id=run_id,
        status="pending",
        stages=[],
        artifacts=[],
        research_payload=None,
        request=request,
    )
    runs[run_id] = state
    return state


def get_run(run_id: str) -> RunState | None:
    return runs.get(run_id)


def update_run(run_id: str, **kwargs: Any) -> RunState | None:
    state = runs.get(run_id)
    if state is None:
        return None
    for k, v in kwargs.items():
        if hasattr(state, k):
            setattr(state, k, v)
    return state


def _find_stage(state: RunState, name: str) -> Stage | None:
    for s in state.stages:
        if s.name == name:
            return s
    return None


def update_stage(
    run_id: str, stage_name: str, status: str, error: str | None = None
) -> Stage | None:
    state = runs.get(run_id)
    if state is None:
        return None
    existing = _find_stage(state, stage_name)
    if existing is None:
        stage = Stage(name=stage_name, status=status, error=error)  # type: ignore[arg-type]
        state.stages.append(stage)
        return stage
    existing.status = status  # type: ignore[assignment]
    existing.error = error
    return existing


def upsert_artifact(run_id: str, artifact: ArtifactMeta) -> ArtifactMeta | None:
    state = runs.get(run_id)
    if state is None:
        return None
    for i, a in enumerate(state.artifacts):
        if a.id == artifact.id:
            state.artifacts[i] = artifact
            return artifact
    state.artifacts.append(artifact)
    return artifact
