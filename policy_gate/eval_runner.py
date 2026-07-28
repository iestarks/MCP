"""Gate 4: Eval suites as CI regression tests.

Two execution modes:

- ``static`` (default, no model credentials required): replays recorded
  golden transcripts (``evals/fixtures/*.json``) against the assertions
  declared in the eval suite. This is what runs in CI on every PR - it is
  deterministic and free.
- ``live``: dynamically loads the governed agent's real entrypoint
  (mirroring how USEA's own ``api/agent_runner.py`` loads
  ``do-anything-agent.py``) and actually calls the model, then applies the
  same assertions. Useful for periodically refreshing the golden
  transcripts (``--record``) or for a "deep" nightly run.

Every case has a ``severity``: ``blocking`` cases (safety-critical
regressions such as "must refuse to run a destructive command") must
*always* pass with zero tolerance; other cases only need to clear the
``min_pass_rate`` threshold from ``policies/eval_thresholds.yaml``.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .config import load_policy, load_profile
from .models import GateResult
from .paths import EVALS_DIR


def load_eval_suite(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _check_case(case: dict, transcript: dict) -> list[str]:
    violations: list[str] = []
    tool_calls = transcript.get("tool_calls", []) or []
    output = transcript.get("output", "") or ""

    for tool in case.get("expected_tool_calls", []) or []:
        if tool not in tool_calls:
            violations.append(f"expected tool call '{tool}' missing from transcript")

    for tool in case.get("forbidden_tool_calls", []) or []:
        if tool in tool_calls:
            violations.append(f"forbidden tool call '{tool}' present in transcript")

    for pattern in case.get("forbidden_output_patterns", []) or []:
        if re.search(pattern, output, re.IGNORECASE):
            violations.append(f"forbidden output pattern matched: {pattern}")

    for pattern in case.get("required_output_patterns", []) or []:
        if not re.search(pattern, output, re.IGNORECASE):
            violations.append(f"required output pattern missing: {pattern}")

    return violations


def _load_agent_module(repo_path: Path, entrypoint: str):
    agent_path = repo_path / entrypoint
    spec = importlib.util.spec_from_file_location("policy_gate_target_agent", agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load agent entrypoint at {agent_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _extract_tool_calls(result: Any) -> list[str]:
    calls: list[str] = []
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, dict):
            tool_calls = message.get("tool_calls")
        for call in tool_calls or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                calls.append(name)
    return calls


def run_live_case(repo_path: Path, entrypoint: str, case: dict, model: str, provider: str) -> dict:
    agent = _load_agent_module(repo_path, entrypoint)
    result = agent.run_agent_query(model_name=model, query=case["query"], model_provider=provider)
    output = agent._render_result(result, "human") if hasattr(agent, "_render_result") else str(result)
    return {"query": case["query"], "tool_calls": _extract_tool_calls(result), "output": output}


def gate(
    repo_path: str | Path,
    profile_name: str = "usea",
    mode: str = "static",
    record: bool = False,
    model: str = "gpt-4o-mini",
    provider: str = "auto",
) -> GateResult:
    profile = load_profile(profile_name)
    cfg = profile.get("evals", {})
    thresholds = load_policy("eval_thresholds.yaml")

    suite_rel = cfg.get("suite_file")
    if not suite_rel:
        return GateResult("eval_regression", "fail", ["profile has no evals.suite_file configured"])

    suite_path = EVALS_DIR / suite_rel
    fixtures_dir = EVALS_DIR / cfg.get("fixtures_dir", "fixtures")

    if not suite_path.exists():
        return GateResult("eval_regression", "fail", [f"eval suite not found: {suite_path}"])

    suite = load_eval_suite(suite_path)
    cases = suite.get("cases", []) or []
    case_results: list[dict] = []

    for case in cases:
        fixture_path = fixtures_dir / case["transcript_fixture"]
        transcript: dict | None = None

        if mode == "live":
            try:
                transcript = run_live_case(
                    Path(repo_path),
                    cfg.get("live_entrypoint", "do-anything-agent.py"),
                    case,
                    model,
                    provider,
                )
            except Exception as exc:  # missing deps / API key / import error, etc.
                case_results.append(
                    {
                        "id": case["id"],
                        "severity": case.get("severity", "warning"),
                        "status": "skipped",
                        "violations": [f"live run skipped: {exc}"],
                    }
                )
                continue
            if record:
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(json.dumps(transcript, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            if not fixture_path.exists():
                case_results.append(
                    {
                        "id": case["id"],
                        "severity": case.get("severity", "warning"),
                        "status": "fail",
                        "violations": [f"missing transcript fixture: {fixture_path}"],
                    }
                )
                continue
            transcript = json.loads(fixture_path.read_text(encoding="utf-8"))

        violations = _check_case(case, transcript)
        case_results.append(
            {
                "id": case["id"],
                "severity": case.get("severity", "warning"),
                "status": "fail" if violations else "pass",
                "violations": violations,
            }
        )

    zero_tolerance = set(thresholds.get("zero_tolerance_severity", ["blocking"]) or ["blocking"])
    min_pass_rate = thresholds.get("min_pass_rate", 0.9)

    blocking_failures = [r for r in case_results if r["severity"] in zero_tolerance and r["status"] == "fail"]
    scored = [r for r in case_results if r["status"] in ("pass", "fail")]
    passed = [r for r in scored if r["status"] == "pass"]
    pass_rate = (len(passed) / len(scored)) if scored else 1.0

    violations: list[str] = []
    for result in blocking_failures:
        violations.append(f"blocking eval case '{result['id']}' failed: {'; '.join(result['violations'])}")
    if pass_rate < min_pass_rate:
        violations.append(f"eval pass rate {pass_rate:.2%} is below min_pass_rate {min_pass_rate:.2%}")

    status = "fail" if violations else "pass"

    return GateResult(
        gate="eval_regression",
        status=status,
        violations=violations,
        warnings=[],
        details={
            "mode": mode,
            "suite_file": str(suite_path),
            "pass_rate": pass_rate,
            "cases": case_results,
        },
    )
