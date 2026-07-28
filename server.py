"""MCP server exposing the AI-SDLC policy-as-code gates as tools.

Run directly (stdio transport, the default for MCP clients):

    python server.py

Or wire it into an MCP client config, e.g. ``configs/usea.mcp.json``:

    {
      "mcpServers": {
        "policy-gate": {
          "command": "python3",
          "args": ["/absolute/path/to/MCP/server.py"]
        }
      }
    }

Each tool mirrors a ``policy_gate.cli`` subcommand so the exact same gate
logic runs whether it is invoked by a human/agent through MCP during
development, or by the ``policy-gate`` CLI in CI.
"""
from __future__ import annotations

from typing import Any

try:
    # mcp SDK >= 2.0: FastMCP was renamed/relocated to mcp.server.mcpserver.MCPServer.
    from mcp.server.fastmcp import FastMCP as _MCPServerClass
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as _MCPServerClass  # type: ignore[no-redef]

from policy_gate import eval_runner, mcp_vetting, prompt_review, tool_manifest

mcp = _MCPServerClass("policy-gate")


@mcp.tool()
def review_prompt(repo_path: str, profile: str = "usea") -> dict[str, Any]:
    """Run the prompt/system-prompt review gate against a checked-out agent repo.

    Extracts the system prompt via static AST analysis (the target file is
    never executed), checks it against forbidden/required regex patterns
    and a max length, and flags any drift from the recorded baseline that
    hasn't been signed off in the prompt review log.
    """
    return prompt_review.gate(repo_path=repo_path, profile_name=profile).to_dict()


@mcp.tool()
def diff_tool_manifest(repo_path: str, profile: str = "usea") -> dict[str, Any]:
    """Diff the agent's tool manifest against the recorded baseline.

    Flags unclassified tools, and any newly added or changed high/critical
    risk tool that lacks a sign-off entry in the tool manifest review log.
    """
    return tool_manifest.gate(repo_path=repo_path, profile_name=profile).to_dict()


@mcp.tool()
def vet_mcp_servers(profile: str = "usea") -> dict[str, Any]:
    """Vet the MCP servers configured for a profile against the allowlist policy.

    Checks launch command allowlisting, version pinning, remote domain
    allowlisting, plaintext secrets in env vars, and required trust-review
    metadata for every configured MCP server.
    """
    return mcp_vetting.gate(profile_name=profile).to_dict()


@mcp.tool()
def run_eval_suite(repo_path: str, profile: str = "usea", mode: str = "static", record: bool = False) -> dict[str, Any]:
    """Run the eval suite as a CI regression test.

    ``mode="static"`` (default) replays recorded golden transcripts with no
    model calls. ``mode="live"`` actually invokes the governed agent; pass
    ``record=True`` to refresh the golden transcripts with the new output.
    """
    return eval_runner.gate(repo_path=repo_path, profile_name=profile, mode=mode, record=record).to_dict()


@mcp.tool()
def run_all_gates(repo_path: str, profile: str = "usea") -> dict[str, Any]:
    """Run every AI-SDLC gate and return an aggregate pass/fail verdict.

    Runs prompt review, tool manifest diffing, MCP server vetting, and the
    eval suite (static mode) in one call - the same set of checks the CI
    workflow enforces on every pull request.
    """
    results = [
        prompt_review.gate(repo_path=repo_path, profile_name=profile).to_dict(),
        tool_manifest.gate(repo_path=repo_path, profile_name=profile).to_dict(),
        mcp_vetting.gate(profile_name=profile).to_dict(),
        eval_runner.gate(repo_path=repo_path, profile_name=profile, mode="static").to_dict(),
    ]
    return {
        "profile": profile,
        "overall_status": "fail" if any(r["status"] == "fail" for r in results) else "pass",
        "gates": results,
    }


if __name__ == "__main__":
    mcp.run()
