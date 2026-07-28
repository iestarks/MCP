from __future__ import annotations

from pathlib import Path

from policy_gate import tool_manifest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_current_manifest_matches_recorded_usea_baseline():
    result = tool_manifest.gate(repo_path=FIXTURES / "usea_repo", profile_name="usea")
    assert result.status == "pass", result.violations + result.warnings
    assert result.details["added"] == []
    assert result.details["removed"] == []
    assert result.details["changed"] == []


def test_new_unclassified_tool_fails_closed():
    result = tool_manifest.gate(repo_path=FIXTURES / "new_tool_repo", profile_name="usea")
    assert result.status == "fail"
    assert any("send_http_request" in v and "no risk classification" in v for v in result.violations)
    assert "send_http_request" in result.details["added"]


def test_extract_tool_manifest_reads_signature_and_docstring(tmp_path):
    source = tmp_path / "agent.py"
    source.write_text(
        "from typing import Any\n"
        "def tool(func: Any) -> Any:\n"
        "    return func\n\n"
        "@tool\n"
        "def echo(message: str, upper: bool = False) -> str:\n"
        "    '''Echo a message back.'''\n"
        "    ...\n",
        encoding="utf-8",
    )
    tools = tool_manifest.extract_tool_manifest(source)
    assert len(tools) == 1
    assert tools[0].name == "echo"
    assert tools[0].description == "Echo a message back."
    assert [p.name for p in tools[0].parameters] == ["message", "upper"]
    assert tools[0].parameters[1].default == "False"
