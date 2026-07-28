from __future__ import annotations

from pathlib import Path

from policy_gate import mcp_vetting
from policy_gate.config import load_policy

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def test_usea_config_passes_vetting():
    policy = load_policy("mcp_server_allowlist.yaml")
    violations, warnings = mcp_vetting.vet_config(CONFIGS / "usea.mcp.json", policy)
    assert violations == [], violations


def test_bad_config_fails_on_every_rule():
    policy = load_policy("mcp_server_allowlist.yaml")
    violations, warnings = mcp_vetting.vet_config(CONFIGS / "bad_example.mcp.json", policy)
    joined = "\n".join(violations)

    assert "shadow-fs" in joined and "literal value" in joined  # hardcoded secret
    assert "mystery-remote" in joined and "allowed_remote_domains" in joined  # disallowed domain
    assert "arbitrary-binary" in joined and "allowed_commands" in joined  # disallowed command
    assert "missing trust_review" in joined  # shadow-fs / mystery-remote have none
    assert len(violations) >= 5


def test_gate_uses_profile_config():
    result = mcp_vetting.gate(profile_name="usea")
    assert result.status == "pass", result.violations
