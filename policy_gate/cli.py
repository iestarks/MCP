"""Command-line entry point for running the AI-SDLC gates outside of MCP.

This is what CI actually invokes (see the ``ai-sdlc-gates.yml`` workflow
added to the USEA repo): it runs the same gate functions the MCP server
exposes as tools, prints a human-readable report, and returns a non-zero
exit code if any gate fails.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import eval_runner, mcp_vetting, prompt_review, tool_manifest
from .models import GateResult

_ICONS = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skipped": "SKIP"}


def _print_result(result: GateResult) -> None:
    label = _ICONS.get(result.status, result.status.upper())
    print(f"[{label}] {result.gate}")
    for violation in result.violations:
        print(f"    VIOLATION: {violation}")
    for warning in result.warnings:
        print(f"    warning:   {warning}")


def _run_all(repo_path: str, profile: str, eval_mode: str) -> list[GateResult]:
    return [
        prompt_review.gate(repo_path, profile),
        tool_manifest.gate(repo_path, profile),
        mcp_vetting.gate(profile),
        eval_runner.gate(repo_path, profile, mode=eval_mode),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="policy-gate", description="AI-SDLC policy-as-code gates for agent repos")
    parser.add_argument("--profile", default="usea", help="governed-agent profile name (default: usea)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser("review-prompt", help="run the prompt/system-prompt review gate")
    p_prompt.add_argument("repo_path")

    p_tools = sub.add_parser("diff-tools", help="run the tool manifest diffing gate")
    p_tools.add_argument("repo_path")

    sub.add_parser("vet-mcp", help="run the MCP server vetting gate")

    p_eval = sub.add_parser("run-evals", help="run the eval suite as a CI regression test")
    p_eval.add_argument("repo_path")
    p_eval.add_argument("--mode", choices=["static", "live"], default="static")
    p_eval.add_argument("--record", action="store_true", help="save live results as new golden fixtures")
    p_eval.add_argument("--model", default="gpt-4o-mini")
    p_eval.add_argument("--model-provider", default="auto")

    p_all = sub.add_parser("check-all", help="run every AI-SDLC gate and print a human-readable report")
    p_all.add_argument("repo_path")
    p_all.add_argument("--eval-mode", choices=["static", "live"], default="static")

    p_json = sub.add_parser("json", help="run every AI-SDLC gate and print a single JSON report")
    p_json.add_argument("repo_path")
    p_json.add_argument("--eval-mode", choices=["static", "live"], default="static")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "review-prompt":
        results = [prompt_review.gate(args.repo_path, args.profile)]
    elif args.command == "diff-tools":
        results = [tool_manifest.gate(args.repo_path, args.profile)]
    elif args.command == "vet-mcp":
        results = [mcp_vetting.gate(args.profile)]
    elif args.command == "run-evals":
        results = [
            eval_runner.gate(
                args.repo_path,
                args.profile,
                mode=args.mode,
                record=args.record,
                model=args.model,
                provider=args.model_provider,
            )
        ]
    elif args.command == "check-all":
        results = _run_all(args.repo_path, args.profile, args.eval_mode)
    elif args.command == "json":
        results = _run_all(args.repo_path, args.profile, args.eval_mode)
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return 1 if any(r.status == "fail" for r in results) else 0
    else:  # pragma: no cover - argparse enforces valid choices
        parser.error(f"unknown command: {args.command}")
        return 2

    for result in results:
        _print_result(result)

    failed = any(r.status == "fail" for r in results)
    if failed:
        print("\nOne or more AI-SDLC gates FAILED. See VIOLATION lines above.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
