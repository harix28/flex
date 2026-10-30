# Planned MLOps Extensions: Continuous Retraining, Tracking & Automated Canary Rollouts

This document outlines the planned future enhancements to the Meridian Sentinel MLOps platform.

## Current State vs Planned Extensions

The **Phase 9 foundation** is implemented in [sentinel/mlops/](../../sentinel/mlops/) and documented in [docs/MLOPS_OPERATIONS.md](../MLOPS_OPERATIONS.md). It provides:
- Immutable model registry in PostgreSQL (`models`, `model_deployments`, `ml_monitoring_runs`)
- SHA-256 bundle verification and safe model loading
- Controlled operator release & rollback CLI (`python -m sentinel.mlops.cli`)
- Inference latency observability (`inference_ms` vs `pipeline_ms`)
- Input feature drift detection against training baseline
- Offline ground-truth evaluation on verified NASA test labels (`RUL_FD001.txt`)

The items below represent **planned extensions** that are not yet implemented.

---

## Planned Capabilities

### 1. Centralized Experiment Tracking (MLflow / Weights & Biases)
- **Current**: Local immutable run artifacts stored in `runs/<version>/` with `report.json` and `bundle.json`.
- **Planned**: Integration with a central MLflow Tracking server to log training runs, hyperparameter sweeps, metric artifacts, and model lineages across distributed training jobs.

### 2. Automated Retraining Pipelines
- **Current**: Offline manual training via `python -m sentinel.train`.
- **Planned**: Orchestrated retraining triggered by detected feature drift or scheduled data refresh, incorporating:
  - Reviewed and frozen data snapshot creation.
  - Automated candidate cross-validation and benchmark comparisons.
  - Hard failure gates: new candidate must strictly outperform existing active model on common validation and official test engines before advancing to candidate registry.

### 3. Automated Canary & Shadow Deployments
- **Current**: Operator-gated release and restart-based activation (`python -m sentinel.mlops.cli deploy` followed by service restart).
- **Planned**:
  - **Shadow Serving**: Route production inference requests simultaneously to active and candidate models; candidate results are logged for observability without affecting application responses.
  - **Canary Rollouts**: Gradually shift inference traffic (e.g. 10% → 50% → 100%) with automated rollback triggers if error rates or latencies exceed defined thresholds.

### 4. Delayed-Label Accuracy Tracking
- **Current**: Offline ground-truth evaluation using verified official test files.
- **Planned**: Continuous tracking of real fleet engines as actual tear-down or failure maintenance occurs, linking actual post-maintenance cycles to historical predictions.
