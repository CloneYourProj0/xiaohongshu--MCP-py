from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_storage_state(path: Path) -> dict | None:
    """Load storage_state JSON from file.

    Returns None if file is missing, empty, whitespace-only, or invalid JSON.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if not text or not text.strip():
            return None
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def save_storage_state(path: Path, state: dict) -> None:
    """Persist storage_state atomically to avoid empty/truncated files."""
    # Ensure state is a dict; fallback to minimal structure if not
    data: dict[str, Any] = state if isinstance(state, dict) else {}
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    _atomic_write(path, payload)
