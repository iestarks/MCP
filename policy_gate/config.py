"""YAML loading helpers for policies and governed-agent profiles."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import POLICIES_DIR, PROFILES_DIR


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


def load_policy(filename: str) -> dict[str, Any]:
    """Load a policy document by filename from the policies/ directory."""
    return load_yaml(POLICIES_DIR / filename)


def load_profile(name: str) -> dict[str, Any]:
    """Load a governed-agent profile by name from the profiles/ directory."""
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Unknown profile '{name}': expected {path} to exist. "
            "Add a profiles/<name>.yaml file to onboard a new governed agent."
        )
    return load_yaml(path)
