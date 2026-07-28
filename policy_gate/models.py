"""Shared result type returned by every gate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GateResult:
    """Outcome of running a single AI-SDLC gate.

    status:
        - "pass": no violations, nothing further required.
        - "warn": no blocking violations, but something needs attention
          (e.g. a brand-new baseline was just recorded, or a tool was
          removed).
        - "fail": one or more blocking violations were found; CI should
          exit non-zero.
        - "skipped": the gate could not run (e.g. live eval mode without
          model credentials) and did not evaluate anything.
    """

    gate: str
    status: str
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status != "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "violations": self.violations,
            "warnings": self.warnings,
            "details": self.details,
        }
