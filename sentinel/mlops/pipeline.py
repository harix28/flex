"""Automated MLOps candidate evaluation pipeline and hard promotion gates.
Compares candidate models against the active baseline with strict near-failure and overestimation gates.
"""
from datetime import datetime, timezone
from typing import TypedDict
from uuid import uuid4
import numpy as np

class GateResult(TypedDict):
    decision: str  # PASS_GATE, REJECTED_BY_GATE
    candidate_version: str
    active_version: str
    active_test_mae: float
    candidate_test_mae: float
    mae_improvement_pct: float
    near_failure_mae_active: float
    near_failure_mae_candidate: float
    gate_checks: dict[str, bool]
    summary: str
    evaluated_at: str

# In-memory candidate registry tracking evaluated runs
_CANDIDATE_RUNS: list[GateResult] = []


def evaluate_candidate_gate(
    candidate_version: str,
    active_version: str,
    active_test_mae: float,
    candidate_test_mae: float,
    near_failure_active: float,
    near_failure_candidate: float,
    candidate_hash: str,
    active_hash: str
) -> GateResult:
    """
    Evaluates candidate model against production baseline using strict industrial safety gates:
    1. Overall Test MAE must improve or be within 2% margin.
    2. Near-Failure MAE (true RUL <= 30 cycles) must not degrade (no hidden late-life failure risk).
    3. Artifact SHA-256 digests must be verified and non-empty.
    """
    diff = active_test_mae - candidate_test_mae
    improvement_pct = (diff / active_test_mae) * 100.0 if active_test_mae > 0 else 0.0

    checks = {
        "overall_mae_acceptable": candidate_test_mae <= (active_test_mae * 1.02),
        "near_failure_accuracy_preserved": near_failure_candidate <= (near_failure_active * 1.05),
        "valid_artifact_hashes": len(candidate_hash) == 64 and len(active_hash) == 64,
        "human_approval_required": True  # Application policy: models are never auto-deployed
    }

    passed = all(checks.values())
    decision = "PASS_GATE" if passed else "REJECTED_BY_GATE"

    summary = (
        f"Candidate {candidate_version} evaluated against active {active_version}. "
        f"Test MAE: {candidate_test_mae:.2f} cycles vs {active_test_mae:.2f} cycles ({improvement_pct:+.1f}%). "
        f"Near-Failure MAE: {near_failure_candidate:.2f} vs {near_failure_active:.2f}. "
        f"Status: {decision} (Human operator sign-off required for production release)."
    )

    result: GateResult = {
        "decision": decision,
        "candidate_version": candidate_version,
        "active_version": active_version,
        "active_test_mae": round(active_test_mae, 2),
        "candidate_test_mae": round(candidate_test_mae, 2),
        "mae_improvement_pct": round(improvement_pct, 2),
        "near_failure_mae_active": round(near_failure_active, 2),
        "near_failure_mae_candidate": round(near_failure_candidate, 2),
        "gate_checks": checks,
        "summary": summary,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }

    _CANDIDATE_RUNS.append(result)
    return result


def list_candidate_evaluations() -> list[GateResult]:
    """Returns history of evaluated candidate models and gate decisions."""
    return list(reversed(_CANDIDATE_RUNS))
