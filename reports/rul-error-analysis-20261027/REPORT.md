# RUL engine-wise error analysis

Date: 2026-10-27

No training, tuning or deployment was performed. Current FD001 and four offline candidates were reloaded with trusted manifest checks. Validation engine IDs were kept disjoint from training and reserved calibration. Official test results are descriptive only; do not use them to select the next experiment.

Error = predicted RUL minus actual RUL. Positive means optimistic remaining-life estimation. All errors are cycles. ±10/±20 percentages are tolerance coverage, not classification accuracy. A 30-cycle diagnostic cutoff is illustrative, not an approved maintenance rule or calibrated failure probability.

## Validation results — use these to plan experiments

| Run | Windows / engines | MAE | RMSE | Bias | Within ±20 | Over by >20 | Missed actual RUL ≤30 |
|---|---|---|---|---|---|---|---|
| fd001-v1 | 90 / 15 | 21.37 | 30.19 | +0.21 | 61.1% | 21.1% | 2 / 18 |
| fd001-20261027-candidate | 90 / 15 | 21.19 | 29.69 | -0.14 | 62.2% | 18.9% | 2 / 18 |
| fd002-20261027-candidate | 234 / 39 | 25.68 | 37.76 | -6.53 | 50.9% | 23.5% | 11 / 50 |
| fd003-20261027-candidate | 90 / 15 | 33.84 | 54.70 | -0.86 | 51.1% | 27.8% | 1 / 19 |
| fd004-20261027-candidate | 222 / 37 | 32.41 | 47.59 | -0.91 | 44.1% | 33.3% | 6 / 43 |

### fd001-v1 — validation life-stage breakdown

| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |
|---|---|---|---|---|---|
| failure_endpoint_0 | 15 / 15 | 7.09 | +7.09 | 93.3% | 6.7% |
| near_failure_1_30 | 3 / 3 | 5.78 | +0.13 | 100.0% | 0.0% |
| remaining_31_60 | 15 / 15 | 11.24 | +3.43 | 86.7% | 13.3% |
| remaining_61_120 | 26 / 15 | 20.68 | +15.59 | 57.7% | 38.5% |
| remaining_over_120 | 31 / 14 | 35.28 | -17.57 | 32.3% | 19.4% |

Largest validation overestimates:

| Engine | Cutoff | Actual RUL | Predicted RUL | Error |
|---|---|---|---|---|
| 45 | 81 | 77 | 137.09 | +60.09 |
| 99 | 61 | 124 | 180.37 | +56.37 |
| 59 | 110 | 121 | 168.13 | +47.13 |
| 89 | 104 | 113 | 153.53 | +40.53 |
| 45 | 55 | 103 | 143.41 | +40.41 |

### fd001-20261027-candidate — validation life-stage breakdown

| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |
|---|---|---|---|---|---|
| failure_endpoint_0 | 15 / 15 | 6.67 | +6.67 | 93.3% | 6.7% |
| near_failure_1_30 | 3 / 3 | 4.39 | -0.37 | 100.0% | 0.0% |
| remaining_31_60 | 15 / 15 | 10.49 | +2.35 | 93.3% | 6.7% |
| remaining_61_120 | 26 / 15 | 20.22 | +14.80 | 53.8% | 38.5% |
| remaining_over_120 | 31 / 14 | 35.83 | -17.15 | 35.5% | 16.1% |

Largest validation overestimates:

| Engine | Cutoff | Actual RUL | Predicted RUL | Error |
|---|---|---|---|---|
| 99 | 61 | 124 | 181.06 | +57.06 |
| 45 | 81 | 77 | 128.19 | +51.19 |
| 59 | 110 | 121 | 165.02 | +44.02 |
| 45 | 55 | 103 | 145.81 | +42.81 |
| 59 | 70 | 161 | 203.73 | +42.73 |

### fd002-20261027-candidate — validation life-stage breakdown

| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |
|---|---|---|---|---|---|
| failure_endpoint_0 | 39 / 39 | 0.21 | +0.21 | 100.0% | 0.0% |
| near_failure_1_30 | 11 / 11 | 26.10 | +26.10 | 27.3% | 72.7% |
| remaining_31_60 | 39 / 39 | 21.89 | +19.74 | 43.6% | 56.4% |
| remaining_61_120 | 70 / 39 | 18.02 | +12.53 | 61.4% | 34.3% |
| remaining_over_120 | 75 / 37 | 47.99 | -46.27 | 22.7% | 1.3% |

Largest validation overestimates:

| Engine | Cutoff | Actual RUL | Predicted RUL | Error |
|---|---|---|---|---|
| 212 | 101 | 48 | 117.91 | +69.91 |
| 212 | 77 | 72 | 129.27 | +57.27 |
| 16 | 104 | 50 | 106.46 | +56.46 |
| 16 | 79 | 75 | 129.65 | +54.65 |
| 212 | 53 | 96 | 147.40 | +51.40 |

### fd003-20261027-candidate — validation life-stage breakdown

| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |
|---|---|---|---|---|---|
| failure_endpoint_0 | 15 / 15 | 6.84 | +6.84 | 100.0% | 0.0% |
| near_failure_1_30 | 4 / 4 | 9.35 | -0.98 | 100.0% | 0.0% |
| remaining_31_60 | 12 / 12 | 21.95 | +18.60 | 58.3% | 41.7% |
| remaining_61_120 | 25 / 15 | 26.56 | +17.21 | 44.0% | 40.0% |
| remaining_over_120 | 34 / 14 | 58.19 | -24.41 | 26.5% | 29.4% |

Largest validation overestimates:

| Engine | Cutoff | Actual RUL | Predicted RUL | Error |
|---|---|---|---|---|
| 89 | 30 | 177 | 363.15 | +186.15 |
| 89 | 100 | 107 | 210.54 | +103.54 |
| 68 | 132 | 69 | 126.08 | +57.08 |
| 45 | 65 | 140 | 195.91 | +55.91 |
| 91 | 105 | 51 | 103.10 | +52.10 |

### fd004-20261027-candidate — validation life-stage breakdown

| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |
|---|---|---|---|---|---|
| failure_endpoint_0 | 37 / 37 | 0.35 | +0.35 | 100.0% | 0.0% |
| near_failure_1_30 | 6 / 6 | 31.99 | +31.99 | 33.3% | 66.7% |
| remaining_31_60 | 34 / 34 | 33.96 | +32.58 | 26.5% | 73.5% |
| remaining_61_120 | 60 / 37 | 31.26 | +26.15 | 35.0% | 60.0% |
| remaining_over_120 | 85 / 35 | 46.58 | -36.27 | 34.1% | 10.6% |

Largest validation overestimates:

| Engine | Cutoff | Actual RUL | Predicted RUL | Error |
|---|---|---|---|---|
| 54 | 96 | 101 | 199.95 | +98.95 |
| 12 | 175 | 97 | 186.72 | +89.72 |
| 54 | 130 | 67 | 155.57 | +88.57 |
| 54 | 163 | 34 | 117.27 | +83.27 |
| 12 | 223 | 49 | 124.86 | +75.86 |

## Official test — descriptive benchmark only

| Run | Evaluated | Short histories excluded | MAE | Within ±10 | Within ±20 |
|---|---|---|---|---|---|
| fd001-v1 | 100 | 0 | 16.79 | 41.0% | 67.0% |
| fd001-20261027-candidate | 100 | 0 | 16.14 | 40.0% | 67.0% |
| fd002-20261027-candidate | 253 | 6 | 21.87 | 37.2% | 57.3% |
| fd003-20261027-candidate | 100 | 0 | 22.07 | 43.0% | 63.0% |
| fd004-20261027-candidate | 237 | 11 | 29.98 | 24.5% | 39.7% |

## Evidence and limits

Recomputed 1516 predictions. Aggregate MAE/RMSE/bias match saved reports within 1e-4; official-test predictions match saved engine-level outputs. No padding, future observations or labels enter inference.
Validation uses the existing six evenly spaced cutoffs per engine. Its coverage is sparse, not every operating cycle; multiple cutoffs of the same engine are correlated. Exact failure endpoints (RUL 0) are shown separately from RUL 1–30. High remaining RUL is not a measured health state.
The validation set already influenced model selection, so it is development evidence rather than an independent generalization claim. Reserved calibration engines remain unused. Official test results have been inspected previously and are not a fresh blind benchmark.
Each engine is identified by run, subset, partition and engine ID. The same numeric engine ID in train/validation and test is a different trajectory. Do not pool these identifiers.
The current FD001 model also appears as a baseline: its examples overlap the FD001 candidate and must not be counted as independent samples in pooled statistics.
Files: cutoff_errors.csv contains every evaluated cutoff; engine_errors.csv contains per-engine aggregates; summary.json contains stage summaries, exclusions, and top over/underestimates.

Reproduce with a new output directory:

```powershell
.venv/Scripts/python.exe scripts/analyze_rul_errors.py --out reports/rul-error-analysis-20261027
```

## Findings and recommended experiment order

1. **Prioritize FD002 and FD004 pre-failure overestimation.** In the existing validation schedule, all 11 FD002 and all 6 FD004 observations with actual RUL 1–30 were predicted above 30 cycles. Their mean errors are +26.10 and +31.99 cycles. By contrast, the exact failure endpoints (39 and 37 observations) have MAE 0.21 and 0.35 after nonnegative clipping. Pooling endpoint and pre-failure cases masks this weakness. These are small, correlated-development samples, not a real-world miss-rate estimate.
2. **Diagnose FD003 outliers before adding model complexity.** Validation engine 89 at cutoff 30 has actual RUL 177 versus predicted 363.15 (+186.15); at cutoff 100, actual 107 versus predicted 210.54 (+103.54). FD003 validation RMSE 54.70 is much higher than MAE 33.84. Investigate this trajectory's training-reference compatibility and sensor/setting distributions without removing hard examples merely to improve the metric.
3. **All candidates struggle with high remaining life.** For actual RUL >120, validation MAE is 35.83/47.99/58.19/46.58 cycles for FD001/2/3/4. This suggests testing richer causal history, but the analysis does not establish a cause or promise an improvement.
4. **Do not claim strong near-failure FD001/FD003 performance from this schedule.** The RUL 1–30 bands contain only 3 and 4 observations. Expand the held-out validation evaluation schedule before choosing a replacement.

### Bounded development plan (not executed in this analysis)

- First freeze a denser validation-only cutoff schedule, including separate RUL 0, 1–30 and 31–60 slices; report engine-balanced errors and engine counts. Correlated windows must not be presented as independent engines. Keep official test and reserved calibration data out of fitting/selection.
- Evaluate 30/50/60-cycle windows with the same existing engine splits. Compare common eligible cutoffs, and separately report history availability; longer windows must not appear better merely by dropping difficult short histories.
- For multi-condition FD002/FD004, compare raw features against operating-condition normalization fitted only on training-engine settings/sensors. Treat its benefit as a hypothesis to test, not an explanation already proved.
- Keep a small predeclared Ridge/XGBoost parameter budget. Retain the constant baseline. Do not use test MAE or test tolerance coverage to select the winner.
- Require improvements in engine-balanced validation RMSE/MAE while checking ±10/±20 coverage, pre-failure misses at the diagnostic 30-cycle cutoff, and overestimation above 20 cycles. Do not promote a candidate with worse pre-failure behavior just because pooled MAE improves. These are development gates; operational acceptance thresholds still require an explicit use case.
- Freeze the chosen method before any final benchmark evaluation. Because this official test set has already been inspected repeatedly, describe subsequent test results as a reused benchmark, not a fresh blind evaluation.

No automatic retraining, model replacement, threshold change or new operational claim was made.
