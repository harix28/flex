"""Unit tests for Phase 6 priority policy, threshold validation, and deterministic input digest."""
import hashlib
import json
import pytest
from sentinel.predictions.policy import PriorityPolicy, DEFAULT_POLICY
from sentinel.predictions.service import compute_input_digest
from sentinel.predictions.schemas import PredictionCreate


def test_priority_policy_threshold_validation():
    # Valid thresholds
    policy = PriorityPolicy(urgent_max=10, high_max=25, medium_max=50)
    assert policy.urgent_max == 10

    # Non-monotonic or negative thresholds fail
    with pytest.raises(ValueError, match='strictly ordered'):
        PriorityPolicy(urgent_max=30, high_max=20, medium_max=50)

    with pytest.raises(ValueError, match='strictly ordered'):
        PriorityPolicy(urgent_max=-5, high_max=20, medium_max=50)

    with pytest.raises(ValueError, match='strictly ordered'):
        PriorityPolicy(urgent_max=20, high_max=20, medium_max=50)


def test_priority_policy_evaluation():
    p = DEFAULT_POLICY
    # urgent <= 15
    band, rule = p.evaluate('available', 10.5)
    assert band == 'urgent'
    assert 'urgent maintenance' in rule

    # boundary 15.0
    band, rule = p.evaluate('available', 15.0)
    assert band == 'urgent'

    # high 15 < x <= 35
    band, rule = p.evaluate('available', 15.1)
    assert band == 'high'
    band, rule = p.evaluate('available', 35.0)
    assert band == 'high'

    # medium 35 < x <= 75
    band, rule = p.evaluate('available', 35.1)
    assert band == 'medium'
    band, rule = p.evaluate('available', 75.0)
    assert band == 'medium'

    # low > 75
    band, rule = p.evaluate('available', 75.1)
    assert band == 'low'
    band, rule = p.evaluate('available', 136.2)
    assert band == 'low'

    # unavailable returns unknown
    band, rule = p.evaluate('unavailable', None, 'insufficient_history')
    assert band == 'unknown'
    assert 'insufficient_history' in rule


def test_input_digest_determinism_and_sensitivity():
    obs1 = [
        [1, [0.1, 0.2, 0.3], [float(i) for i in range(21)]],
        [2, [0.1, 0.2, 0.3], [float(i + 1) for i in range(21)]],
    ]
    digest1 = compute_input_digest(obs1)
    digest1_again = compute_input_digest(obs1)
    assert digest1 == digest1_again
    assert len(digest1) == 64

    # Any value change produces distinct digest
    obs2 = [
        [1, [0.1, 0.2, 0.3], [float(i) for i in range(21)]],
        [2, [0.1, 0.2, 0.3], [float(i + 1.01) for i in range(21)]],
    ]
    digest2 = compute_input_digest(obs2)
    assert digest1 != digest2

    # Cycle order change or setting change produces distinct digest
    obs3 = [
        [1, [0.1, 0.25, 0.3], [float(i) for i in range(21)]],
        [2, [0.1, 0.2, 0.3], [float(i + 1) for i in range(21)]],
    ]
    assert compute_input_digest(obs3) != digest1


def test_prediction_request_schema():
    # Valid cutoff
    req = PredictionCreate(cutoff_cycle=50)
    assert req.cutoff_cycle == 50

    # Omitted cutoff
    req2 = PredictionCreate()
    assert req2.cutoff_cycle is None

    # Invalid cutoffs
    with pytest.raises(Exception):
        PredictionCreate(cutoff_cycle=0)

    with pytest.raises(Exception):
        PredictionCreate(cutoff_cycle=-1)

    # Extra fields forbidden
    with pytest.raises(Exception):
        PredictionCreate(cutoff_cycle=30, extra_sensor=123)
