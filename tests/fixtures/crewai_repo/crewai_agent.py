"""Fixture mirroring a minimal CrewAI research-and-automation agent.

Only the parts that matter for static AST analysis (the @tool-decorated
functions and the agent_backstory assembly) are reproduced here. This file
is intentionally never executed — only parsed — so it has no runtime
dependencies (no crewai import required).
"""
from __future__ import annotations

from typing import Any


def tool(func: Any) -> Any:
    return func


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of the top results for the given query."""
    ...


@tool
def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a UTF-8 file from the local filesystem and return its contents."""
    ...


@tool
def execute_python(code: str, timeout_seconds: int = 30) -> str:
    """Execute a Python code snippet in a sandboxed subprocess and return stdout/stderr."""
    ...


agent_backstory = (
    "You are a research and automation assistant. "
    "You have access to web search, file reading, and Python code execution tools.\n\n"
    "Always explain risk before executing code or reading sensitive files. "
    "Mask any sensitive values, API keys, or credentials in your responses. "
    "Never print or expose secrets or tokens.\n\n"
    "General Policy:\n"
    "1) Use only the minimum tools required to answer a request.\n"
    "2) If risky, explain the risk first, then proceed with minimum necessary action.\n"
    "3) If unclear, ask one focused follow-up question.\n"
    "4) Mask sensitive values and never expose raw credentials.\n"
    "5) Return a concise summary with: request, actions taken, outputs, and next steps."
)


def run_crew(query: str, model: str = "gpt-4o-mini") -> dict[str, Any]:
    """Entry point for live eval mode; not used during static analysis."""
    return {"messages": []}
