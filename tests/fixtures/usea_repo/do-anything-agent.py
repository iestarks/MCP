"""Fixture mirroring the relevant excerpt of USEA's do-anything-agent.py.

Only the parts that matter for static AST analysis (the @tool-decorated
functions and the system_content assembly) are reproduced here. This file
is intentionally never executed - only parsed - so it has no runtime
dependencies (no langchain import required).
"""
from __future__ import annotations

from typing import Any

from api.access_control import disclosure_policy


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


@tool
def recall_prior_prompts(query: str = "", limit: int = 5) -> str:
    """Recall prior prompts and responses from local encrypted memory, optionally filtered by a search query."""
    ...


MEMORY_AVAILABLE = True


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
        system_content += disclosure_policy(False)

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

        if MEMORY_AVAILABLE:
            system_content += (
                "Local Memory Policy:\n"
                "1) Relevant prior prompts/responses may already be auto-recalled as "
                "context below; use them only if truly relevant, otherwise ignore.\n"
                "2) Call recall_prior_prompts (optionally with a search query) to look "
                "up more local history yourself, e.g. when the user references something "
                "not already shown.\n"
                "3) Stored history is encrypted at rest on the local machine and is never "
                "sent to LangSmith or any third party.\n\n"
            )

        system_content += (
            "General Policy:\n"
            "1) If actionable, execute minimal required steps and verify outcomes.\n"
            "2) If risky, explain risk first, then do minimum necessary action.\n"
            "3) If a user reply is short (e.g. 'Yes', 'No', 'Sure', 'Go ahead', 'Ok'), "
            "treat it as a direct confirmation or continuation of the most recent "
            "assistant question or suggestion in the conversation history and act on it "
            "immediately. Do NOT ask for further clarification. Do NOT say the reply is "
            "'recurring', 'ambiguous', or 'without context' -- just act on it.\n"
            "4) If the conversation history is empty and the intent is genuinely unclear, "
            "ask exactly one short, specific follow-up question (e.g. 'What topic or "
            "resource would you like more details on?'). Never describe the user's message "
            "as a 'recurring query'.\n"
            "5) Mask sensitive values and never output full raw secrets.\n"
            "6) Return concise summary with: request, actions, outputs, next checks.\n"
            "7) Keep output short and practical."
        )
    return {"messages": []}
