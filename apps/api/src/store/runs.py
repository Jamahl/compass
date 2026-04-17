"""SQLite-backed run store.

Persists :class:`RunState` across process restarts. The module preserves the
exact public API of the previous in-memory implementation so the rest of the
codebase (routes, orchestrator) needs no changes apart from the new
:func:`list_runs` helper.

Design notes
------------
* The database file lives at ``<repo>/apps/api/data/runs.db``. The directory
  is created on import if missing.
* Each call opens a fresh :class:`sqlite3.Connection` via :func:`_conn` with
  ``check_same_thread=False`` — simpler than juggling a shared connection and
  cheap enough for the volumes this MVP handles.
* A module-level :class:`threading.Lock` (``_LOCK``) serialises every public
  operation. This keeps read-modify-write sequences (stage/artifact upserts)
  atomic without relying on SQLite transactions spanning multiple statements.
* Pydantic models are serialised with ``model_dump(mode="json")`` so the
  resulting JSON round-trips cleanly back through ``model_validate``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import ArtifactMeta, RunRequest, RunState, Stage

# ---- Paths / schema --------------------------------------------------------
# This file lives at apps/api/src/store/runs.py. ``parents`` indices:
#   [0]=store, [1]=src, [2]=api, [3]=apps, [4]=repo root.
# The DB belongs under apps/api/data/, so parents[2] is the right anchor.
_DB_PATH: Path = Path(__file__).resolve().parents[2] / "data" / "runs.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    status           TEXT NOT NULL,
    request_json     TEXT NOT NULL,
    stages_json      TEXT NOT NULL DEFAULT '[]',
    artifacts_json   TEXT NOT NULL DEFAULT '[]',
    research_payload TEXT
);
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_runs_created_at "
    "ON runs(created_at DESC);"
)

_LOCK = threading.Lock()

# Fields on RunState that callers are allowed to mutate via update_run().
_UPDATABLE_FIELDS: frozenset[str] = frozenset({"status", "research_payload"})


def _conn() -> sqlite3.Connection:
    """Return a fresh SQLite connection with row access by name."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Create the data directory, table, and index if they don't exist."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.execute(_INDEX_SQL)
        conn.commit()


_init_db()


# ---- (De)serialisation helpers --------------------------------------------
def _row_to_state(row: sqlite3.Row) -> RunState:
    """Hydrate a DB row into a :class:`RunState`."""
    request_data = json.loads(row["request_json"]) if row["request_json"] else None
    stages_data = json.loads(row["stages_json"] or "[]")
    artifacts_data = json.loads(row["artifacts_json"] or "[]")
    return RunState.model_validate(
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "stages": stages_data,
            "artifacts": artifacts_data,
            "research_payload": row["research_payload"],
            "request": request_data,
        }
    )


def _get_state_locked(conn: sqlite3.Connection, run_id: str) -> RunState | None:
    """Load a single run by id. Caller must already hold ``_LOCK``."""
    cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    return _row_to_state(row) if row is not None else None


# ---- Public API ------------------------------------------------------------
def create_run(run_id: str, request: RunRequest) -> RunState:
    """Insert a new pending run and return its freshly-built state."""
    created_at = datetime.now(timezone.utc).isoformat()
    state = RunState(
        run_id=run_id,
        created_at=created_at,
        status="pending",
        stages=[],
        artifacts=[],
        research_payload=None,
        request=request,
    )
    request_json = json.dumps(request.model_dump(mode="json"))
    with _LOCK, _conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, created_at, status,
                request_json, stages_json, artifacts_json, research_payload
            ) VALUES (?, ?, ?, ?, '[]', '[]', NULL)
            """,
            (run_id, created_at, "pending", request_json),
        )
        conn.commit()
    return state


def get_run(run_id: str) -> RunState | None:
    """Return the full :class:`RunState` for ``run_id`` or ``None``."""
    with _LOCK, _conn() as conn:
        return _get_state_locked(conn, run_id)


def update_run(run_id: str, **kwargs: Any) -> RunState | None:
    """Mutate whitelisted fields on an existing run and persist the result.

    Unknown kwargs are silently ignored (preserves historical behaviour).
    Returns the updated state or ``None`` if the run doesn't exist.
    """
    with _LOCK, _conn() as conn:
        state = _get_state_locked(conn, run_id)
        if state is None:
            return None
        for key, value in kwargs.items():
            if key in _UPDATABLE_FIELDS and hasattr(state, key):
                setattr(state, key, value)
        conn.execute(
            "UPDATE runs SET status = ?, research_payload = ? WHERE run_id = ?",
            (state.status, state.research_payload, run_id),
        )
        conn.commit()
    return state


def _find_stage(state: RunState, name: str) -> Stage | None:
    """Return the first stage with ``name`` on ``state`` or ``None``."""
    for stage in state.stages:
        if stage.name == name:
            return stage
    return None


def update_stage(
    run_id: str,
    stage_name: str,
    status: str,
    error: str | None = None,
) -> Stage | None:
    """Create-or-update a named stage on ``run_id`` and return it."""
    with _LOCK, _conn() as conn:
        state = _get_state_locked(conn, run_id)
        if state is None:
            return None
        existing = _find_stage(state, stage_name)
        if existing is None:
            stage = Stage(name=stage_name, status=status, error=error)  # type: ignore[arg-type]
            state.stages.append(stage)
            result: Stage = stage
        else:
            existing.status = status  # type: ignore[assignment]
            existing.error = error
            result = existing
        stages_json = json.dumps(
            [s.model_dump(mode="json") for s in state.stages]
        )
        conn.execute(
            "UPDATE runs SET stages_json = ? WHERE run_id = ?",
            (stages_json, run_id),
        )
        conn.commit()
    return result


def upsert_artifact(
    run_id: str, artifact: ArtifactMeta
) -> ArtifactMeta | None:
    """Insert or replace an artifact (matched by id) on ``run_id``."""
    with _LOCK, _conn() as conn:
        state = _get_state_locked(conn, run_id)
        if state is None:
            return None
        replaced = False
        for idx, existing in enumerate(state.artifacts):
            if existing.id == artifact.id:
                state.artifacts[idx] = artifact
                replaced = True
                break
        if not replaced:
            state.artifacts.append(artifact)
        artifacts_json = json.dumps(
            [a.model_dump(mode="json") for a in state.artifacts]
        )
        conn.execute(
            "UPDATE runs SET artifacts_json = ? WHERE run_id = ?",
            (artifacts_json, run_id),
        )
        conn.commit()
    return artifact


def list_runs(limit: int = 50) -> list[RunState]:
    """Return up to ``limit`` runs, newest first, as hydrated :class:`RunState`."""
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
    return [_row_to_state(row) for row in rows]
