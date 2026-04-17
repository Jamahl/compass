"""Env config loader.

Loads the root-level .env (two directories up from this file) via python-dotenv
and exposes the three API keys as module-level constants. Raises ValueError if
any required key is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Root .env lives at: <repo>/.env  (this file is at <repo>/apps/api/src/config.py)
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
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
