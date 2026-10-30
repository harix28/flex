"""Unit tests for ML telemetry dynamics and NASA asymmetric evaluation metrics."""
import pytest
import numpy as np
from sentinel.ml.benchmark import (
    nasa_asymmetric_penalty,
    nasa_asymmetric_score,
    compute_regression_metrics,
)
from sentinel.ml.dynamics import (
    compute_sensor_drift,
    compute_kurtosis,
    calculate_operating_regime,
    extract_trajectory_features,
)


def test_nasa_asymmetric_penalty_late_vs_early():
    # An error of 10 cycles late should be penalized more severely than 10 cycles early
    early_err = -10.0
    late_err = 10.0
    
    early_penalty = nasa_asymmetric_penalty(early_err)
    late_penalty = nasa_asymmetric_penalty(late_err)
    
    assert early_penalty > 0.0
    assert late_penalty > 0.0
    assert late_penalty > early_penalty
    assert np.isclose(early_penalty, np.exp(10.0 / 13.0) - 1.0)
    assert np.isclose(late_penalty, np.exp(10.0 / 10.0) - 1.0)


def test_nasa_asymmetric_score_perfect():
    y_true = np.array([50.0, 75.0, 100.0, 120.0])
    y_pred = np.array([50.0, 75.0, 100.0, 120.0])
    score = nasa_asymmetric_score(y_true, y_pred)
    assert score == 0.0


def test_nasa_asymmetric_score_shape_mismatch():
    with pytest.raises(ValueError, match="shapes must match"):
        nasa_asymmetric_score(np.array([1.0, 2.0]), np.array([1.0]))


def test_compute_regression_metrics_structure():
    y_true = np.array([100.0, 80.0, 60.0, 40.0])
    y_pred = np.array([95.0, 82.0, 58.0, 45.0])
    
    metrics = compute_regression_metrics(y_true, y_pred)
    
    assert "rmse" in metrics
    assert "mae" in metrics
    assert "mape_percent" in metrics
    assert "nasa_score" in metrics
    assert "mean_nasa_score" in metrics
    assert metrics["sample_size"] == 4
    assert metrics["early_predictions_count"] == 2
    assert metrics["late_predictions_count"] == 2
    assert 0.0 <= metrics["safety_margin_ratio"] <= 1.0


def test_sensor_drift_linear():
    # Linear ramp y = 2 * t
    t = np.arange(10, dtype=float).reshape(-1, 1)
    y = 2.0 * t
    slopes = compute_sensor_drift(y)
    assert np.isclose(slopes[0], 2.0)


def test_kurtosis_normal_distribution():
    np.random.seed(42)
    # Kurtosis of normal is approximately 0 (Fisher excess kurtosis)
    samples = np.random.randn(5000, 2)
    kurt = compute_kurtosis(samples)
    assert np.all(np.abs(kurt) < 0.5)


def test_kurtosis_flat_signal_safety():
    # Invariant sensor reading should not produce NaN or ZeroDivisionError
    flat = np.ones((30, 5), dtype=float) * 42.0
    kurt = compute_kurtosis(flat)
    assert np.all(kurt == 0.0)


def test_calculate_operating_regime():
    assert calculate_operating_regime(2.0, 0.1, 80.0) == 0
    assert calculate_operating_regime(12.0, 0.3, 85.0) == 1
    assert calculate_operating_regime(12.0, 0.6, 90.0) == 2
    assert calculate_operating_regime(22.0, 0.7, 95.0) == 3
    assert calculate_operating_regime(35.0, 0.7, 100.0) == 4
    assert calculate_operating_regime(35.0, 0.82, 100.0) == 5


def test_extract_trajectory_features_shape():
    window = np.ones((30, 24), dtype=float)
    features = extract_trajectory_features(window)
    # 24 * 5 = 120 features (last, mean, std, slope, kurtosis)
    assert features.shape == (120,)
    assert np.isfinite(features).all()

