from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return sha256_digest(content.encode("utf-8"))
