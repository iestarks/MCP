"""Gate 3: MCP server vetting.

Validates the MCP server configuration a governed agent (or its editor /
runtime) would load - the same shape as a Claude Desktop / VS Code
``mcp.json`` file - against an allowlist policy:

- launch ``command`` must be on an allowlist (no arbitrary binaries)
- ``npx``/``uvx`` invocations must be pinned to a version (no "latest")
- remote (``url``) servers must target an allowed domain
- env vars that look like secrets must use ``${VAR}`` expansion, never a
  literal value committed to the config
- every server entry must carry a ``trust_review`` block naming a human
  reviewer

This directly addresses "unvetted / malicious MCP server" risk - a
server with a benign-looking name but an unpinned install command or a
hardcoded credential is exactly the kind of supply-chain issue this gate
is meant to catch before it is wired into an agent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .config import load_policy, load_profile
from .models import GateResult
from .paths import CONFIGS_DIR


def vet_config(config_path: Path, policy: dict) -> tuple[list[str], list[str]]:
    """Vet a single MCP server config file against ``policy``.

    Returns ``(violations, warnings)``. Kept separate from :func:`gate` so
    it can be unit tested against arbitrary config files.
    """
    violations: list[str] = []
    warnings: list[str] = []

    if not config_path.exists():
        return [f"MCP server config not found: {config_path}"], warnings

    data = json.loads(config_path.read_text(encoding="utf-8"))
    servers = data.get("mcpServers") or data.get("servers") or {}

    if not servers:
        warnings.append("no MCP servers declared in config")
        return violations, warnings

    allowed_commands = set(policy.get("allowed_commands", []) or [])
    allowed_domains = set(policy.get("allowed_remote_domains", []) or [])
    secret_patterns = [re.compile(p, re.IGNORECASE) for p in (policy.get("secret_env_key_patterns") or [])]
    require_pinned = bool(policy.get("require_pinned_version", True))
    require_trust_review = bool(policy.get("require_trust_review", True))

    for name, entry in servers.items():
        command = entry.get("command")
        args = entry.get("args") or []
        url = entry.get("url")
        env = entry.get("env") or {}
        trust_review = entry.get("trust_review")

        if require_trust_review and not trust_review:
            violations.append(f"[{name}] missing trust_review metadata (reviewer/date/notes)")

        if not command and not url:
            violations.append(f"[{name}] entry has neither 'command' nor 'url'")

        if command:
            if command not in allowed_commands:
                violations.append(f"[{name}] command '{command}' is not in allowed_commands allowlist")
            if require_pinned and command in ("npx", "uvx"):
                joined_args = " ".join(str(a) for a in args)
                if not re.search(r"@[\w.\-]+|==[\w.\-]+", joined_args):
                    violations.append(
                        f"[{name}] '{command}' invocation is not pinned to a version "
                        "(add @version or ==version to the package argument)"
                    )

        if url:
            host = urlparse(url).hostname or ""
            if host not in allowed_domains:
                violations.append(f"[{name}] remote url host '{host}' is not in allowed_remote_domains")

        for key, value in env.items():
            if any(pattern.search(key) for pattern in secret_patterns):
                is_expansion = isinstance(value, str) and value.startswith("${") and value.endswith("}")
                if not is_expansion:
                    violations.append(
                        f"[{name}] env var '{key}' looks like a secret but has a literal value; "
                        'use "${VAR_NAME}" expansion instead of committing the value'
                    )

    return violations, warnings


def gate(profile_name: str = "usea") -> GateResult:
    profile = load_profile(profile_name)
    cfg = profile.get("mcp_servers", {})
    policy = load_policy("mcp_server_allowlist.yaml")

    config_rel = cfg.get("config_file")
    config_path = (CONFIGS_DIR / config_rel) if config_rel else None

    if config_path is None:
        return GateResult("mcp_server_vetting", "fail", ["profile has no mcp_servers.config_file configured"])

    violations, warnings = vet_config(config_path, policy)
    status = "fail" if violations else ("warn" if warnings else "pass")

    return GateResult(
        gate="mcp_server_vetting",
        status=status,
        violations=violations,
        warnings=warnings,
        details={"config_file": str(config_path)},
    )
