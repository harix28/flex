"""Maintenance priority rules, policy versioning, and transparent RUL evaluation."""
from dataclasses import dataclass
from typing import Literal

PriorityBand = Literal['urgent', 'high', 'medium', 'low', 'unknown']

DEFAULT_POLICY_VERSION = 'v1-experimental'
DISCLAIMER = 'Experimental simulation thresholds; not manufacturer-approved operational limits'


@dataclass(frozen=True)
class PriorityPolicy:
    version: str = DEFAULT_POLICY_VERSION
    urgent_max: float = 15.0
    high_max: float = 35.0
    medium_max: float = 75.0
    units: str = 'cycles'
    disclaimer: str = DISCLAIMER

    def __post_init__(self):
        if not (0 < self.urgent_max < self.high_max < self.medium_max):
            raise ValueError('Priority thresholds must be strictly ordered: 0 < urgent_max < high_max < medium_max')

    def evaluate(self, status: str, rul_cycles: float | None, reason: str | None = None) -> tuple[PriorityBand, str]:
        """Maps an estimated RUL or unavailable status to a named priority band and explanation."""
        if status != 'available' or rul_cycles is None:
            r = reason or 'unavailable'
            return 'unknown', f'Prediction unavailable ({r}): priority unknown; inspection required'
        if rul_cycles <= self.urgent_max:
            return 'urgent', f'Estimated RUL {rul_cycles:.1f} cycles <= {self.urgent_max:.0f} cycles: urgent maintenance inspection recommended'
        if rul_cycles <= self.high_max:
            return 'high', f'Estimated RUL {rul_cycles:.1f} cycles <= {self.high_max:.0f} cycles: high priority maintenance scheduling'
        if rul_cycles <= self.medium_max:
            return 'medium', f'Estimated RUL {rul_cycles:.1f} cycles <= {self.medium_max:.0f} cycles: medium priority monitoring'
        return 'low', f'Estimated RUL {rul_cycles:.1f} cycles > {self.medium_max:.0f} cycles: low priority / normal operational tracking'

    def as_dict(self):
        return {
            'policy_version': self.version,
            'urgent_max_cycles': self.urgent_max,
            'high_max_cycles': self.high_max,
            'medium_max_cycles': self.medium_max,
            'units': self.units,
            'disclaimer': self.disclaimer,
        }


DEFAULT_POLICY = PriorityPolicy()
