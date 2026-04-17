"""Env config loader.

Loads the root-level .env (two directories up from this file) via python-dotenv
and exposes the three API keys as module-level constants. Raises ValueError if
any required key is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _find_dotenv() -> Path | None:
    """Find a repo-root .env relative to this file.

    Works in two layouts:
      * host dev: apps/api/src/config.py → parents[3] is <repo>.
      * docker:   /app/src/config.py     → there's no parents[3]. In that case
        docker-compose's env_file already injected the keys into the process
        environment, so we return None and rely on os.getenv.
    """
    here = Path(__file__).resolve()
    for p in here.parents:
        candidate = p / ".env"
        if candidate.is_file():
            return candidate
    return None


ROOT_ENV = _find_dotenv()
if ROOT_ENV is not None:
    load_dotenv(ROOT_ENV)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY")
AUTOCONTENT_API_KEY = os.getenv("AUTOCONTENT_API_KEY")


def require_keys() -> None:
    missing = [
        name
        for name, val in [
            ("OPENAI_API_KEY", OPENAI_API_KEY),
            ("PARALLEL_API_KEY", PARALLEL_API_KEY),
            ("AUTOCONTENT_API_KEY", AUTOCONTENT_API_KEY),
        ]
        if not val
    ]
    if missing:
        raise ValueError(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Set them in {ROOT_ENV}"
        )
