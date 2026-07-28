"""Gate 1: Prompt / system-prompt review.

Statically extracts the system prompt text assembled by a governed agent
(via AST parsing - the target file is never imported or executed) and
checks it against a policy-as-code rule set:

- forbidden regex patterns (prompt-injection / jailbreak phrasing, "leak
  the secret" style instructions, etc.)
- required regex patterns (e.g. an explicit masking/redaction instruction)
- a maximum length
- a baseline diff: if the extracted prompt differs from the recorded
  baseline, the PR must also log a reviewer entry, otherwise the gate
  fails. This turns silent prompt drift into a visible, blocking event.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .config import load_policy, load_profile
from .models import GateResult
from .paths import BASELINES_DIR


def _literal_text(node: ast.AST | None) -> str | None:
    """Best-effort constant-folding of string literals and ``+`` concatenation."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_text(node.left)
        right = _literal_text(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def extract_system_prompt(source_path: Path, variable_name: str = "system_content") -> str:
    """Reconstruct the full text assigned/appended to ``variable_name``.

    Statements are ordered by source line number (not AST traversal order),
    so conditional branches (e.g. ``if vault_enabled: system_content +=
    ...``) are reconstructed in the same top-to-bottom order a human reading
    the file would see them.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    chunks: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        target_name: str | None = None
        value_node: ast.AST | None = None

        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            value_node = node.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value_node = node.value

        if target_name != variable_name:
            continue

        text = _literal_text(value_node)
        if text is not None:
            chunks.append((node.lineno, text))

    chunks.sort(key=lambda item: item[0])
    return "".join(text for _, text in chunks)


def gate(repo_path: str | Path, profile_name: str = "usea") -> GateResult:
    profile = load_profile(profile_name)
    prompt_cfg = profile.get("prompt", {})
    policy = load_policy("prompt_policy.yaml")
    review_log = load_policy("prompt_review_log.yaml")

    target_file = prompt_cfg.get("target_file", "do-anything-agent.py")
    variable_name = prompt_cfg.get("variable_name", "system_content")
    source_path = Path(repo_path) / target_file

    if not source_path.exists():
        return GateResult("prompt_review", "fail", [f"target file not found: {source_path}"])

    try:
        extracted = extract_system_prompt(source_path, variable_name)
    except SyntaxError as exc:
        return GateResult("prompt_review", "fail", [f"failed to parse {source_path}: {exc}"])

    if not extracted.strip():
        return GateResult(
            "prompt_review",
            "fail",
            [f"no assignments to '{variable_name}' were found in {source_path}; nothing to review"],
        )

    violations: list[str] = []
    warnings: list[str] = []

    for rule in policy.get("forbidden_patterns", []) or []:
        if re.search(rule["pattern"], extracted, re.IGNORECASE):
            violations.append(f"forbidden pattern matched ({rule['pattern']}): {rule.get('reason', '')}")

    for rule in policy.get("required_patterns", []) or []:
        if not re.search(rule["pattern"], extracted, re.IGNORECASE):
            violations.append(f"required pattern missing ({rule['pattern']}): {rule.get('reason', '')}")

    max_len = policy.get("max_length_chars")
    if max_len and len(extracted) > max_len:
        violations.append(f"prompt is {len(extracted)} chars, exceeds max_length_chars={max_len}")

    baseline_rel = prompt_cfg.get("baseline_file")
    baseline_path = (BASELINES_DIR / baseline_rel) if baseline_rel else None
    baseline_text = None
    if baseline_path is not None and baseline_path.exists():
        baseline_text = baseline_path.read_text(encoding="utf-8")

    is_new_baseline = baseline_path is not None and baseline_text is None
    changed = baseline_text is not None and baseline_text.strip() != extracted.strip()

    if changed and policy.get("require_reviewer_log_on_change", True):
        entries = review_log.get("entries") or []
        signed_off = any(entry.get("baseline") == baseline_rel for entry in entries)
        if not signed_off:
            violations.append(
                f"system prompt changed from baseline '{baseline_rel}' with no matching entry in "
                f"policies/prompt_review_log.yaml. Update the baseline file and log a reviewer entry "
                "to intentionally accept this change."
            )

    if is_new_baseline:
        warnings.append(
            f"no baseline recorded yet at {baseline_path}; once reviewed, save the extracted prompt "
            "there so future changes are diffed against it."
        )

    status = "fail" if violations else ("warn" if (is_new_baseline or warnings) else "pass")

    return GateResult(
        gate="prompt_review",
        status=status,
        violations=violations,
        warnings=warnings,
        details={
            "source_file": str(source_path),
            "variable_name": variable_name,
            "extracted_length": len(extracted),
            "baseline_file": str(baseline_path) if baseline_path else None,
            "changed_from_baseline": changed,
            "extracted_prompt_preview": extracted[:400],
        },
    )
