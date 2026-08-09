from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


def run_dir(run_id: str, base: str | Path = "runs") -> Path:
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise ValueError("run_id may contain only letters, digits, dash and underscore")
    p = Path(base) / run_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    p.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: str | Path) -> Any:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw.get("data", raw)
