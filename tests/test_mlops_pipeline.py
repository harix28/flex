"""Unit tests for Automated MLOps Candidate Evaluation Gates and Shadow Serving."""
from sentinel.mlops.pipeline import evaluate_candidate_gate, list_candidate_evaluations
from sentinel.mlops.shadow import ShadowServingManager


def test_candidate_promotion_gate_evaluation():
    # 1. Superior candidate passing gate
    good = evaluate_candidate_gate(
        candidate_version="fd001-v2-xgboost-candidate",
        active_version="fd001-v1",
        active_test_mae=16.14,
        candidate_test_mae=14.80,  # Improved
        near_failure_active=4.00,
        near_failure_candidate=3.80, # Improved near-failure
        candidate_hash="a" * 64,
        active_hash="b" * 64
    )
    assert good["decision"] == "PASS_GATE"
    assert good["mae_improvement_pct"] > 0
    assert good["gate_checks"]["overall_mae_acceptable"] is True
    assert good["gate_checks"]["near_failure_accuracy_preserved"] is True

    # 2. Regressed candidate failing gate (near failure accuracy degraded)
    bad = evaluate_candidate_gate(
        candidate_version="fd001-v2-flawed-candidate",
        active_version="fd001-v1",
        active_test_mae=16.14,
        candidate_test_mae=18.50, # Degraded
        near_failure_active=4.00,
        near_failure_candidate=7.50, # Severe near-failure degradation
        candidate_hash="c" * 64,
        active_hash="b" * 64
    )
    assert bad["decision"] == "REJECTED_BY_GATE"
    assert bad["gate_checks"]["overall_mae_acceptable"] is False
    assert bad["gate_checks"]["near_failure_accuracy_preserved"] is False

    # 3. Candidate history
    history = list_candidate_evaluations()
    assert len(history) >= 2
    assert history[0]["candidate_version"] == "fd001-v2-flawed-candidate"


def test_shadow_serving_divergence_metrics():
    mgr = ShadowServingManager()
    mgr.configure(enabled=True, version="fd001-shadow-v2")

    # Record some predictions (active vs shadow)
    mgr.record_divergence(active_pred=20.0, shadow_pred=21.5)  # 1.5 diff
    mgr.record_divergence(active_pred=45.0, shadow_pred=44.0)  # 1.0 diff
    mgr.record_divergence(active_pred=12.0, shadow_pred=14.0)  # 2.0 diff

    metrics = mgr.get_metrics()
    assert metrics["shadow_enabled"] is True
    assert metrics["shadow_version"] == "fd001-shadow-v2"
    assert metrics["total_comparisons"] == 3
    assert metrics["mean_absolute_divergence_cycles"] == 1.50
    assert metrics["max_divergence_cycles"] == 2.00
