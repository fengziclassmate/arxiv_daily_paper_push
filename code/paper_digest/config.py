from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def project_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or project_dir() / "config.json"
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_env_file(path: Path | None = None) -> None:
    env_path = path or project_dir() / ".env"
    if not env_path.exists():
        return
    with env_path.open("r", encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
