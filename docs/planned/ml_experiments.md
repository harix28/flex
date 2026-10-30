# Planned ML Research: Calibration, Multi-Horizon Classification & Neural Architectures

This document specifies the planned machine learning research directions and model candidate progressions for Meridian Sentinel.

## Current ML Status

- **Implemented**: Causal sensor feature extraction ($W=30$ cycles, 96 features) in [sentinel/features.py](../../sentinel/features.py). Uncapped RUL regression via XGBoost/Ridge in [sentinel/train.py](../../sentinel/train.py). Active verified model `fd001-v1` in `runs/fd001-v1/`.
- **Experimental Offline Candidates**: Four-subset candidate runs (`runs/fd001-20261027-candidate` through `fd004-...`) and 54-fit history-window experiment in [sentinel/rul_experiments.py](../../sentinel/rul_experiments.py).
- **Rejected Candidate**: Cap-125 candidate was tested on official test engines, failed the improvement gate (MAE 13.58 vs baseline 12.45), and was explicitly not promoted (see [reports/FD001_CAP125_COMPARISON_20261028.md](../../reports/FD001_CAP125_COMPARISON_20261028.md)).

---

## Planned Research & Candidate Progression

### 1. Probability Calibration & Uncertainty Intervals
- **Problem**: Current models output discrete cycle estimates ($\text{RUL} \in \mathbb{R}^+$). The application does not output learned failure probabilities.
- **Rule**: Rescaling an RUL estimate into $[0, 1]$ is strictly prohibited and must NEVER be reported as a failure probability.
- **Planned Work**:
  - Independent engine-grouped conformal prediction intervals with bounded width and verified test coverage.
  - Well-calibrated survival models / hazard rate estimators fit on held-out calibration engines, evaluated via Brier score and reliability curves.

### 2. Multi-Horizon Classification
- **Task**: Explicit classification of binary failure event within horizon $H$:
  $$P(\text{RUL} \le H \mid \text{observed history } W)$$
  with proposed evaluation horizons $H \in \{15, 30, 45\}$ flight cycles.
- **Advancement Criteria**: Must outperform naive baseline and demonstrate monotonicity across horizons before operational deployment.

### 3. Sequential Deep Learning Architectures
- **Candidates**: Temporal Convolutional Networks (TCN), Bidirectional GRU/LSTM, or Time-Series Transformers.
- **Requirements**: Must provide statistically significant MAE improvement over regularized gradient-boosted trees on official NASA test benchmarks while maintaining real-time inference latency under 50ms per window.

### 4. Automated Feature Selection & Dimensionality Reduction
- **Status**: Comprehensive EDA and validated automated feature selection are **not yet implemented**.
- **Current Approach**: Uses expert domain knowledge and causal trailing statistics (mean, standard deviation, min, max, slope) across the 21 physical sensors and 3 operational settings.
- **Planned**: Systematic ablation studies, SHAP attribution stability checks across engine operating regimes, and formal feature selection pipelines.
