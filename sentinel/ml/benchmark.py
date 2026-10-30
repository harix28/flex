"""NASA C-MAPSS benchmark metrics and asymmetric scoring functions."""
from typing import Dict, Any
import numpy as np


def nasa_asymmetric_penalty(d: float) -> float:
    """Compute asymmetric NASA penalty for an individual prediction error d = y_pred - y_true.
    
    If d < 0 (early prediction): penalty = exp(-d / 13) - 1
    If d >= 0 (late prediction):  penalty = exp(d / 10) - 1
    
    Late predictions receive a steeper exponential penalty due to flight safety risk.
    """
    if d < 0.0:
        return float(np.exp(-d / 13.0) - 1.0)
    else:
        return float(np.exp(d / 10.0) - 1.0)


def nasa_asymmetric_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute total NASA C-MAPSS asymmetric evaluation score across fleet engines.
    
    Args:
        y_true: Ground truth RUL cycles array (1D).
        y_pred: Predicted RUL cycles array (1D).
    Returns:
        Cumulative score (lower is better, 0 is perfect).
    """
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    if yt.shape != yp.shape:
        raise ValueError("Ground truth and prediction shapes must match")
    if len(yt) == 0:
        return 0.0
    
    d = yp - yt
    penalties = np.where(d < 0, np.exp(-d / 13.0) - 1.0, np.exp(d / 10.0) - 1.0)
    return float(np.sum(penalties))


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Compute comprehensive turbofan maintenance regression metrics."""
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    if yt.shape != yp.shape or len(yt) == 0:
        raise ValueError("Invalid metric input arrays")

    d = yp - yt
    rmse = float(np.sqrt(np.mean(d ** 2)))
    mae = float(np.mean(np.abs(d)))
    
    # Avoid zero division for percentage error
    safe_yt = np.maximum(yt, 1.0)
    mape = float(np.mean(np.abs(d) / safe_yt) * 100.0)
    
    total_score = nasa_asymmetric_score(yt, yp)
    early_count = int(np.sum(d < 0))
    late_count = int(np.sum(d >= 0))
    
    return {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mape_percent": round(mape, 2),
        "nasa_score": round(total_score, 2),
        "mean_nasa_score": round(total_score / len(yt), 4),
        "sample_size": len(yt),
        "early_predictions_count": early_count,
        "late_predictions_count": late_count,
        "safety_margin_ratio": round(early_count / len(yt), 4) if len(yt) > 0 else 0.0,
    }
