"""Fixture that adds an unclassified critical-risk tool, used to prove the
tool manifest diffing gate fails closed on undeclared capability creep."""
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


@tool
def send_http_request(url: str, method: str = "GET") -> str:
    """Send an arbitrary outbound HTTP request and return the response body."""
    ...
