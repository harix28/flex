"""Sensor trajectory dynamics, kurtosis, and operating regime extraction for C-MAPSS."""
from typing import Tuple
import numpy as np
from sentinel.data import SENSORS, SETTINGS, VALUES


def compute_sensor_drift(window_matrix: np.ndarray) -> np.ndarray:
    """Compute rate of change (first difference slope) across trailing cycles.
    
    Args:
        window_matrix: 2D numpy array of shape (N, num_features).
    Returns:
        1D numpy array of slope per feature.
    """
    if window_matrix.ndim != 2 or len(window_matrix) < 2:
        raise ValueError("Window matrix must have at least 2 observations")
    t = np.arange(len(window_matrix), dtype=np.float64)
    t_norm = t - t.mean()
    denom = np.dot(t_norm, t_norm)
    if denom == 0.0:
        return np.zeros(window_matrix.shape[1], dtype=np.float64)
    return np.dot(t_norm, window_matrix) / denom


def compute_kurtosis(values: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Compute Fisher-Pearson excess kurtosis along axis 0 for sensor vibration signals.
    
    Protects against zero division on invariant signals (e.g. static setting or flat sensors).
    """
    if len(values) < 4:
        return np.zeros(values.shape[1], dtype=np.float64)
    mean = np.mean(values, axis=0)
    diff = values - mean
    var = np.mean(diff ** 2, axis=0)
    std = np.sqrt(var)
    with np.errstate(divide='ignore', invalid='ignore'):
        m4 = np.mean(diff ** 4, axis=0)
        kurt = np.where(std > eps, (m4 / (var ** 2 + eps)) - 3.0, 0.0)
    return np.nan_to_num(kurt, nan=0.0, posinf=0.0, neginf=0.0)


def calculate_operating_regime(setting_1: float, setting_2: float, setting_3: float) -> int:
    """Classify C-MAPSS flight operational condition into one of the 6 canonical flight envelopes.
    
    Settings represent:
    - setting_1: Altitude (0 - 42 kft)
    - setting_2: Mach Number (0.0 - 0.84)
    - setting_3: Throttle Resolver Angle (TRA, 60 - 100)
    """
    # Regime boundaries based on NASA C-MAPSS technical memo
    if setting_1 < 5.0:
        return 0  # Sea level / low altitude take-off / climb
    elif setting_1 < 15.0:
        return 1 if setting_2 < 0.4 else 2  # Low-mid cruise vs acceleration
    elif setting_1 < 28.0:
        return 3  # High-subsonic climb
    else:
        return 4 if setting_2 < 0.75 else 5  # High-altitude cruise vs dash


def extract_trajectory_features(window_data: np.ndarray) -> np.ndarray:
    """Extract complete dynamic feature vector: last, mean, std, slope, kurtosis.
    
    Input:
        window_data: 2D array of shape (window_length, len(VALUES))
    Returns:
        1D vector of concatenated dynamic features.
    """
    arr = np.asarray(window_data, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != len(VALUES) or len(arr) < 2:
        raise ValueError(f"Expected array of shape (>=2, {len(VALUES)})")
    if not np.isfinite(arr).all():
        raise ValueError("Observations must contain finite numbers")

    last_val = arr[-1]
    mean_val = np.mean(arr, axis=0)
    std_val = np.std(arr, axis=0)
    slopes = compute_sensor_drift(arr)
    kurt = compute_kurtosis(arr)

    return np.concatenate([last_val, mean_val, std_val, slopes, kurt])

