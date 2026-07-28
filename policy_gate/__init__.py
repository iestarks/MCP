"""policy_gate: Policy-as-code AI-SDLC gates for governed LLM agent repos.

Exposes four gates - prompt/system-prompt review, tool manifest diffing,
MCP server vetting, and eval-suite regression testing - both as an MCP
server (see ``server.py``) and as a CLI (see ``policy_gate.cli``).
"""
from __future__ import annotations

__version__ = "0.1.0"
