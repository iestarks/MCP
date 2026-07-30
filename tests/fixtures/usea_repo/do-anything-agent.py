"""Fixture mirroring the relevant excerpt of USEA's do-anything-agent.py.

Only the parts that matter for static AST analysis (the @tool-decorated
functions and the system_content assembly) are reproduced here. This file
is intentionally never executed - only parsed - so it has no runtime
dependencies (no langchain import required).
"""
from __future__ import annotations

from typing import Any


def tool(func: Any) -> Any:
    return func


@tool
def run_command(command: str, timeout_seconds: int = 120) -> str:
    """Run a shell command and return exit code, stdout, and stderr."""
    ...


@tool
def list_directory(path: str = ".") -> str:
    """List files and folders for a given directory path."""
    ...


@tool
def read_text_file(path: str, max_chars: int = 12000) -> str:
    """Read a UTF-8 text file and return its contents."""
    ...


@tool
def write_text_file(path: str, content: str, append: bool = False) -> str:
    """Write UTF-8 text content to a file."""
    ...


def _run_with_fallback(
    instruction: str,
    model_name: str,
    model_provider: str,
    model_candidates: list[str] | None,
    vault_enabled: bool = False,
    vault_simulate: bool = True,
    privacy_mode: bool = False,
) -> dict[str, Any]:
    for candidate in ["gpt-4o-mini"]:
        system_content = "You are a universal operations agent. Handle instructions and queries for any context using available tools.\n\n"

        if vault_enabled:
            system_content += (
                "Vault Operations Policy (when Vault tools available):\n"
                "1) Call get_cluster_snapshot first to assess cluster health.\n"
                "2) If failed_azs is non-empty, do NOT unseal nodes in failed AZs. "
                "Only unseal sealed healthy nodes in surviving AZs.\n"
                "3) If single node is unhealthy outside full AZ outage, seal it if reachable.\n"
                "4) Always call fetch_keyvault_metadata before any unseal_node call.\n"
                "5) Never emit full raw credentials - mask trailing characters.\n"
                "6) If risky, explain the risk before proceeding.\n\n"
            )

        if privacy_mode:
            system_content += (
                "Local Privacy Mode Policy:\n"
                "1) Do not read, quote, or summarize the contents of credential/secret files "
                "(.env, keys, tokens, cloud credentials).\n"
                "2) Do not run commands that dump environment variables or credentials.\n"
                "3) Keep the response self-contained; do not suggest sending data to any "
                "external service beyond what is required to answer.\n\n"
            )

        system_content += (
            "General Policy:\n"
            "1) If actionable, execute minimal required steps and verify outcomes.\n"
            "2) If risky, explain risk first, then do minimum necessary action.\n"
            "3) If unclear, ask one focused follow-up question.\n"
            "4) Mask sensitive values and never output full raw secrets.\n"
            "5) Return concise summary with: request, actions, outputs, next checks.\n"
            "6) Keep output short and practical."
        )
    return {"messages": []}
