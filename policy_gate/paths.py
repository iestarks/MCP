"""Central path constants for the policy-gate repo layout.

This module intentionally resolves everything relative to the repository
root (one level above the ``policy_gate`` package) rather than bundling
data files inside the Python package. Policies, baselines, profiles and
eval fixtures are meant to be reviewed as plain-text diffs in pull
requests, so they live next to the code, not inside a wheel.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

PROFILES_DIR = REPO_ROOT / "profiles"
POLICIES_DIR = REPO_ROOT / "policies"
BASELINES_DIR = REPO_ROOT / "baselines"
EVALS_DIR = REPO_ROOT / "evals"
CONFIGS_DIR = REPO_ROOT / "configs"
