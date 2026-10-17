"""Kaagaz backend.

On import, settings from the repo's `.env` file (if it exists) are added to the environment, without overriding
anything already set. So `uvicorn`, the benchmark and the MCP server pick up a local LLM key, while tests and
verify.sh, which set LLM_* to empty on purpose, keep running with no key.
"""

import os
from pathlib import Path

_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_dotenv(path: Path = _ENV) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()
