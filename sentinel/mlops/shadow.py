"""Shadow serving and active-vs-candidate prediction divergence tracker.
Runs candidate model inference in parallel to observe real-world performance without affecting user responses.
"""
from typing import TypedDict
from datetime import datetime, timezone
import numpy as np

class ShadowMetrics(TypedDict):
    shadow_enabled: bool
    shadow_version: str | None
    total_comparisons: int
    mean_absolute_divergence_cycles: float
    p95_divergence_cycles: float
    max_divergence_cycles: float
    last_evaluated_at: str | None


class ShadowServingManager:
    def __init__(self):
        self.enabled = False
        self.shadow_version: str | None = None
        self.divergences: list[float] = []
        self.last_evaluated_at: str | None = None

    def configure(self, enabled: bool, version: str | None = None):
        self.enabled = enabled
        self.shadow_version = version if enabled else None
        if not enabled:
            self.divergences.clear()

    def record_divergence(self, active_pred: float, shadow_pred: float):
        if not self.enabled:
            return
        div = abs(active_pred - shadow_pred)
        self.divergences.append(div)
        self.last_evaluated_at = datetime.now(timezone.utc).isoformat()
        # Cap window at 500 records
        if len(self.divergences) > 500:
            self.divergences.pop(0)

    def get_metrics(self) -> ShadowMetrics:
        if not self.divergences:
            return {
                "shadow_enabled": self.enabled,
                "shadow_version": self.shadow_version,
                "total_comparisons": 0,
                "mean_absolute_divergence_cycles": 0.0,
                "p95_divergence_cycles": 0.0,
                "max_divergence_cycles": 0.0,
                "last_evaluated_at": self.last_evaluated_at
            }
        arr = np.array(self.divergences)
        return {
            "shadow_enabled": self.enabled,
            "shadow_version": self.shadow_version,
            "total_comparisons": len(self.divergences),
            "mean_absolute_divergence_cycles": round(float(np.mean(arr)), 2),
            "p95_divergence_cycles": round(float(np.percentile(arr, 95)), 2),
            "max_divergence_cycles": round(float(np.max(arr)), 2),
            "last_evaluated_at": self.last_evaluated_at
        }


shadow_manager = ShadowServingManager()

