from __future__ import annotations

RISK_LEVELS = ("read_only", "low", "high", "destructive")


def requires_approval(risk_level: str) -> bool:
    return risk_level in ("high", "destructive")


def requires_two_approvals(risk_level: str) -> bool:
    return risk_level == "destructive"
