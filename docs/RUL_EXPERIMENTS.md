# Offline RUL experiments and uncertainty

Implemented 2026-10-27. This is a separate offline evaluation path; the current serving model and database prediction contract are unchanged.

## Results and decision

The frozen 54-fit experiment selected 60-cycle XGBoost models for all four subsets, with training-only operating-condition normalization for FD002/FD004. Independent audit MAE changed from 16.46 to 12.04 (FD001), 25.94 to 15.79 (FD002), 25.01 to 25.28 (FD003), and 29.60 to 19.03 (FD004), in cycles. FD003 did not improve on this independent audit.

Engine-group conformal intervals are implemented, but mean audit widths are 165.8–232.7 cycles. FD003 whole-engine audit coverage is 83.3% on six engines, below the nominal 90% target. Broad intervals and small audit samples prevent treating these as precise maintenance guidance. Coverage is not classification accuracy or an individual engine's failure probability.

See [full protocol, metrics and actual predictions](../reports/rul-improvement-20261027/REPORT.md) and [machine-readable results](../reports/rul-improvement-20261027/summary.json). Calibration and audit partitions have now been used; future studies must acknowledge this when assessing independence. Previously inspected official test data is a reused benchmark, not fresh blind evidence.

## Run a verified prediction

From the repository root, with local validated NASA files already present:

```powershell
.venv/Scripts/python.exe scripts/predict_rul_experiment.py --bundle runs/rul-improvement-20261027/FD001 --trusted-sha256 055bc444010cd2aa4062e399f3663d1c384f2b5c29468baf5fd4f5aa08c780e8 --subset FD001 --engine 3
```

This actual test-engine example returns approximately 60.01 cycles with interval 0–178.73 cycles. The CLI does not read official RUL labels. Use `--partition train` or `--cutoff` for an explicit history selection. Fewer than 60 readings returns unavailable for these selected models. No zero padding or invented timestamps are used.

The trusted hash authenticates the offline manifest, which binds model, transformation and interval hashes. Obtain hashes for other subsets from the recorded results. Do not accept a hash supplied alongside an untrusted downloaded model as independent trust.

## Verification and reproduction

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_pipeline.py tests/test_rul_experiments.py
.venv/Scripts/python.exe scripts/run_rul_improvement.py --out runs/rul-improvement-20261027
```

The tests passed: 18 total. The training command was executed successfully; it refuses an existing output directory. An intentional repeat requires a new versioned output path. Each selected model was reloaded and checked against every eligible official-test prediction. Existing model/configuration hashes were preserved. No production integration or full application regression was performed for this offline milestone.

## Integration handoff

- `sentinel/rul_experiments.py`: causal windows, training-only transforms, weighted selection metrics, engine-group calibration, independent audit and verified offline predictor.
- `scripts/run_rul_improvement.py`: frozen candidate grid, selection before calibration/audit/test, immutable output directory and reload checks.
- `scripts/predict_rul_experiment.py`: explicit local inference without fitting or labels.
- `tests/test_rul_experiments.py`: leakage, grouping, finite-sample quantile, selection guardrails and artifact/input validation.
- `runs/rul-improvement-20261027`: ignored local model artifacts; portable evidence is in the reports directory.

Before serving, explicitly implement and test per-subset routing, normalized-feature parity, interval metadata and tenant-scoped persistence. The experimental manifest intentionally uses a separate schema from production. Model promotion remains a reviewed action. A future uncertainty study should predeclare its method and evaluation evidence before tuning; do not revise calibration based on these audit results and then report the same audit as independent.
