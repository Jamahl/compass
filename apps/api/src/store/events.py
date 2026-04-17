"""Per-run event log — append-only stream for the live "thinking" UI.

Events are short, structured records produced by the orchestrator, the writer,
and the upstream tool wrappers (Parallel, OpenAI, AutoContent). They are
intentionally separate from `runs.stages` (which is a small finite-state list)
so we can stream verbose narration, tool calls, and errors without polluting
the run state model.

Schema
------
id          INTEGER PK AUTOINCREMENT  — monotonic sequence used by clients
                                        as a "since" cursor for incremental polling
run_id      TEXT NOT NULL
ts          TEXT NOT NULL             — ISO 8601 UTC
level       TEXT NOT NULL             — "debug" | "info" | "warn" | "error"
source      TEXT NOT NULL             — emitter (e.g. "runner", "parallel", "llm")
type        TEXT NOT NULL             — short tag (e.g. "stage.start", "tool.call")
message     TEXT NOT NULL             — human-readable line
data_json   TEXT                      — optional JSON blob with extra fields

The append helper swallows all exceptions: logging must NEVER break a run.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Mirrors the path strategy used by store/runs.py.
# parents: [0]=store, [1]=src, [2]=api, [3]=apps, [4]=repo root
_DB_PATH: Path = Path(__file__).resolve().parents[2] / "data" / "events.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL,
    ts        TEXT NOT NULL,
    level     TEXT NOT NULL DEFAULT 'info',
    source    TEXT NOT NULL,
    type      TEXT NOT NULL,
    message   TEXT NOT NULL,
    data_json TEXT
);
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_events_run_id_id "
    "ON events(run_id, id);"
)

_LOCK = threading.Lock()
_VALID_LEVELS = {"debug", "info", "warn", "error"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.execute(_INDEX_SQL)
        conn.commit()


_init_db()


def append_event(
    run_id: str,
    source: str,
    type: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """Append an event. Never raises — logging must not break the run."""
    try:
        if level not in _VALID_LEVELS:
            level = "info"
        ts = datetime.now(timezone.utc).isoformat()
        data_json = json.dumps(data, default=str) if data else None
        with _LOCK, _conn() as conn:
            conn.execute(
                "INSERT INTO events (run_id, ts, level, source, type, message, data_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, ts, level, source, type, message, data_json),
            )
            conn.commit()
    except Exception:
        # Intentionally swallow — telemetry must not break the run.
        pass


def list_events(run_id: str, since: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
    """Return events for a run with id > ``since`` (ascending), capped at ``limit``."""
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            "SELECT id, run_id, ts, level, source, type, message, data_json "
            "FROM events WHERE run_id = ? AND id > ? "
            "ORDER BY id ASC LIMIT ?",
            (run_id, int(since), int(limit)),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(row["data_json"]) if row["data_json"] else None
        out.append(
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "ts": row["ts"],
                "level": row["level"],
                "source": row["source"],
                "type": row["type"],
                "message": row["message"],
                "data": data,
            }
        )
    return out
