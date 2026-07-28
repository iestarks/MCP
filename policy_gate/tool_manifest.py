"""Gate 2: Tool manifest diffing.

Statically extracts the signature of every tool exposed to the agent
(any function decorated with ``@tool`` by default) via AST parsing, then
diffs it against a recorded JSON baseline. Every tool must carry an
explicit risk classification in ``policies/tool_manifest_policy.yaml``;
new or changed tools at a "review required" risk tier must also have a
sign-off entry in ``policies/tool_manifest_review_log.yaml``.

This is what catches "tool poisoning" / silent capability creep: an
agent quietly gaining a new high-blast-radius tool (shell exec,
unrestricted file write, network egress, etc.) without a human ever
having reviewed it.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import load_policy, load_profile
from .models import GateResult
from .paths import BASELINES_DIR


@dataclass
class ToolParameter:
    name: str
    annotation: str | None
    default: str | None


@dataclass
class ToolSignature:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)


def _annotation_to_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    return ast.unparse(node)


def _has_target_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef, decorator_name: str) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == decorator_name:
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == decorator_name:
            return True
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == decorator_name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == decorator_name:
                return True
    return False


def extract_tool_manifest(source_path: Path, decorator_name: str = "tool") -> list[ToolSignature]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    tools: list[ToolSignature] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _has_target_decorator(node, decorator_name):
            continue

        docstring = ast.get_docstring(node) or ""
        args = node.args
        positional = args.args
        defaults = list(args.defaults)
        padded_defaults: list[ast.AST | None] = [None] * (len(positional) - len(defaults)) + defaults  # type: ignore[list-item]

        parameters = [
            ToolParameter(
                name=arg.arg,
                annotation=_annotation_to_str(arg.annotation),
                default=_annotation_to_str(default) if default is not None else None,
            )
            for arg, default in zip(positional, padded_defaults)
        ]

        tools.append(ToolSignature(name=node.name, description=docstring.strip(), parameters=parameters))

    return sorted(tools, key=lambda tool: tool.name)


def _tool_to_dict(tool: ToolSignature) -> dict:
    data = asdict(tool)
    return data


def manifest_to_json(tools: list[ToolSignature]) -> str:
    return json.dumps([_tool_to_dict(t) for t in tools], indent=2, sort_keys=True)


def diff_manifest(current: dict[str, dict], baseline: dict[str, dict]) -> dict[str, list[str]]:
    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    changed = sorted(name for name in (set(current) & set(baseline)) if current[name] != baseline[name])
    return {"added": added, "removed": removed, "changed": changed}


def gate(repo_path: str | Path, profile_name: str = "usea") -> GateResult:
    profile = load_profile(profile_name)
    cfg = profile.get("tool_manifest", {})
    policy = load_policy("tool_manifest_policy.yaml")
    review_log = load_policy("tool_manifest_review_log.yaml")

    target_file = cfg.get("target_file", "do-anything-agent.py")
    decorator_name = cfg.get("decorator_name", "tool")
    source_path = Path(repo_path) / target_file

    if not source_path.exists():
        return GateResult("tool_manifest_diff", "fail", [f"target file not found: {source_path}"])

    try:
        current_tools = extract_tool_manifest(source_path, decorator_name)
    except SyntaxError as exc:
        return GateResult("tool_manifest_diff", "fail", [f"failed to parse {source_path}: {exc}"])

    current_by_name = {t.name: _tool_to_dict(t) for t in current_tools}

    baseline_rel = cfg.get("baseline_file")
    baseline_path = (BASELINES_DIR / baseline_rel) if baseline_rel else None
    baseline_tools: list[dict] = []
    if baseline_path is not None and baseline_path.exists():
        baseline_tools = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_by_name = {t["name"]: t for t in baseline_tools}

    diff = diff_manifest(current_by_name, baseline_by_name)

    classified = policy.get("tools", {}) or {}
    review_required_tiers = set(policy.get("review_required_risk_tiers", []) or [])
    entries = review_log.get("entries") or []

    def has_signoff(tool_name: str) -> bool:
        return any(
            entry.get("tool") == tool_name and entry.get("profile", profile_name) == profile_name
            for entry in entries
        )

    violations: list[str] = []
    warnings: list[str] = []

    for name in sorted(current_by_name):
        if name not in classified:
            violations.append(f"tool '{name}' has no risk classification in policies/tool_manifest_policy.yaml")

    for name in diff["added"]:
        tier = (classified.get(name) or {}).get("risk")
        if tier in review_required_tiers and not has_signoff(name):
            violations.append(
                f"new tool '{name}' (risk={tier}) requires a sign-off entry in "
                "policies/tool_manifest_review_log.yaml before it can ship"
            )

    for name in diff["changed"]:
        tier = (classified.get(name) or {}).get("risk")
        if tier in review_required_tiers and not has_signoff(name):
            violations.append(
                f"tool '{name}' signature/description changed (risk={tier}) and requires a sign-off entry "
                "in policies/tool_manifest_review_log.yaml"
            )

    for name in diff["removed"]:
        warnings.append(f"tool '{name}' is recorded in the baseline but is no longer exposed by the agent")

    is_new_baseline = not baseline_tools
    if is_new_baseline:
        warnings.append(f"no baseline recorded yet at {baseline_path}; nothing to diff against")

    status = "fail" if violations else ("warn" if (is_new_baseline or warnings) else "pass")

    return GateResult(
        gate="tool_manifest_diff",
        status=status,
        violations=violations,
        warnings=warnings,
        details={
            "source_file": str(source_path),
            "current_tools": sorted(current_by_name),
            "added": diff["added"],
            "removed": diff["removed"],
            "changed": diff["changed"],
            "baseline_file": str(baseline_path) if baseline_path else None,
        },
    )
