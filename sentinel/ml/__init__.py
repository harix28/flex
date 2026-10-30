"""Meridian Sentinel Machine Learning & Telemetry Dynamics Package."""
from .dynamics import (
    compute_sensor_drift,
    calculate_operating_regime,
    compute_kurtosis,
    extract_trajectory_features,
)
from .benchmark import (
    nasa_asymmetric_penalty,
    nasa_asymmetric_score,
    compute_regression_metrics,
)

__all__ = [
    "compute_sensor_drift",
    "calculate_operating_regime",
    "compute_kurtosis",
    "extract_trajectory_features",
    "nasa_asymmetric_penalty",
    "nasa_asymmetric_score",
    "compute_regression_metrics",
]
