from __future__ import annotations

from pathlib import Path

from policy_gate import prompt_review

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_extracted_prompt_matches_recorded_usea_baseline():
    """The bundled usea baseline must match what static analysis extracts
    from a faithful reproduction of do-anything-agent.py's system prompt."""
    result = prompt_review.gate(repo_path=FIXTURES / "usea_repo", profile_name="usea")
    assert result.status == "pass", result.violations + result.warnings
    assert result.details["changed_from_baseline"] is False


def test_forbidden_jailbreak_pattern_fails_closed():
    result = prompt_review.gate(repo_path=FIXTURES / "bad_prompt_repo", profile_name="usea")
    assert result.status == "fail"
    assert any("forbidden pattern matched" in v for v in result.violations)


def test_missing_target_file_fails():
    result = prompt_review.gate(repo_path=FIXTURES, profile_name="usea")
    assert result.status == "fail"
    assert "target file not found" in result.violations[0]


def test_extract_system_prompt_orders_by_source_line(tmp_path):
    source = tmp_path / "agent.py"
    source.write_text(
        "def f():\n"
        "    system_content = 'A'\n"
        "    if True:\n"
        "        system_content += 'B'\n"
        "    system_content += 'C'\n",
        encoding="utf-8",
    )
    assert prompt_review.extract_system_prompt(source) == "ABC"
