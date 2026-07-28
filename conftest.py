"""Ensures the ``policy_gate`` package is importable without an editable
install, e.g. when running ``pytest`` directly from a fresh clone."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
