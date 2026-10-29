# Better-validated RUL and tested uncertainty — offline milestone

Date: 2026-10-27

Completed 54 predeclared candidate fits across FD001–FD004. All four selected candidates passed the validation development gate. No model was deployed and no production prediction/API contract was changed. Uncertainty is implemented and measured offline, but the resulting intervals are broad; this is not a claim of precise or production-ready confidence bounds.

## Dense validation comparison

All comparisons below use the same observed cutoffs from cycle 60 onward, with equal total weight per engine. Baseline means the previous 20261027 candidate for that subset, not the running historical FD001-v1 model. This is a different evaluation schedule from the earlier six-cutoff or official-test reports.

| Subset | Selected | Validation windows / engines | MAE before → after | RMSE before → after | ±20 coverage before → after | Near-failure miss before → after |
|---|---|---|---|---|---|---|
| FD001 | raw-w60-xgboost_1 | 2275 / 15 | 17.22 → 13.45 | 23.55 → 19.10 | 68.0% → 78.0% | 8.7% → 7.1% |
| FD002 | condition_normalized-w60-xgboost_1 | 5865 / 39 | 21.87 → 14.39 | 28.59 → 20.99 | 54.0% → 76.2% | 31.8% → 10.4% |
| FD003 | raw-w60-xgboost_1 | 2803 / 15 | 27.98 → 25.23 | 42.00 → 40.22 | 54.7% → 59.5% | 15.3% → 8.2% |
| FD004 | condition_normalized-w60-xgboost_1 | 6469 / 37 | 30.58 → 20.11 | 40.31 → 29.51 | 41.0% → 66.1% | 36.3% → 15.1% |

MAE/RMSE are cycles. Near-failure means actual RUL 1–30, excluding the exact failure endpoint; a diagnostic miss is predicted RUL >30. This is an illustrative development threshold, not an approved maintenance rule or failure probability.

## Independent audit — not used to select or calibrate

| Subset | Audit engines | Point MAE before → after | Whole-engine interval coverage | Engine-balanced window coverage | Mean interval width (cycles) |
|---|---|---|---|---|---|
| FD001 | 6 | 16.46 → 12.04 | 100.0% | 100.0% | 190.6 |
| FD002 | 15 | 25.94 → 15.79 | 100.0% | 100.0% | 165.8 |
| FD003 | 6 | 25.01 → 25.28 | 83.3% | 97.8% | 231.9 |
| FD004 | 15 | 29.60 → 19.03 | 100.0% | 100.0% | 232.7 |

Nominal target: 90% coverage for an exchangeable engine trajectory on the declared cutoff schedule. Observed audit coverage can differ, especially with only six audit engines in FD001/FD003. Whole-engine coverage requires every evaluated cutoff of an engine to be covered. It must not be confused with a percentage of correct point predictions.

The wide intervals are a substantive limitation. High coverage achieved with broad ranges does not establish a useful maintenance decision boundary. Do not display the nominal 90% as a guaranteed probability for one engine or as failure risk.

## Frozen protocol and data separation

- Existing training/validation/reserved-calibration engine IDs were preserved. Model and normalization fitting used training engines only.
- Predeclared 30/50/60-cycle windows; Ridge(alpha100), XGBoost(depth3,250 estimators) and XGBoost(depth5,350 estimators). Raw features on all subsets; six-condition normalization additionally tested on FD002/FD004. Total fits: 54.
- At most 100 evenly spaced training cutoffs per engine from cycle60. Validation evaluates every cycle from60. All models see the same validation targets/cutoffs; longer windows cannot win by dropping short validation windows.
- Normalization: scale operating settings and fit six KMeans groups on training engines only; normalize sensors by training-group mean/std. Zero-variance scales become1. No missing readings are filled.
- Gate: both engine-balanced MAE and RMSE must decrease, ±20 coverage must not decrease, and overall >20-cycle overestimation, pre-failure misses and pre-failure >20-cycle overestimation must not increase. Lowest RMSE among passing candidates wins; otherwise retain the baseline.
- Selection metadata and model hashes were frozen before opening reserved calibration/audit partitions or official test data.
- Reserved engines were shuffled with seed43: first max(9,ceil(0.6*n)) used for calibration, remainder for independent audit. No refit/recalibration after audit.
- Interval score: maximum absolute point residual per calibration engine over eligible cycles>=60. Finite-sample rank ceil((n+1)*0.9) selects the calibration radius. Too few engines yields unavailable, not a fabricated finite bound. Lower bound is clipped at0.
- Engine groups address dependence within trajectories, but guarantees still require exchangeable engines and a matching cutoff population. Official test truncation is a distribution shift and only measured descriptively.
- Calibration/audit partitions have now been consumed for this experiment. They must no longer be described as unused independent evidence in subsequent development cycles.

Method reference: [Angelopoulos and Bates, A Gentle Introduction to Conformal Prediction](https://arxiv.org/abs/2107.07511). Group-max scoring and the cutoff protocol are explicitly defined above; no universal coverage under drift is claimed.

## Reused official benchmark — not used for selection

| Subset | Common test engines (cycle≥60) | Common MAE before → after | Selected point-eligible engines / total | Excluded point histories | Excluded interval histories |
|---|---|---|---|---|---|
| FD001 | 88 | 15.01 → 12.45 | 88 / 100 | 12 | 12 |
| FD002 | 221 | 20.53 → 13.72 | 221 / 259 | 38 | 38 |
| FD003 | 94 | 21.25 → 16.40 | 94 / 100 | 6 | 6 |
| FD004 | 222 | 30.31 → 19.26 | 222 / 248 | 26 | 26 |

All selected models require60 readings. The availability loss relative to the previous30-cycle models is reported, not hidden. No padding or interpolated readings were introduced. Benchmark results have already been inspected in earlier work and are not a fresh blind evaluation.

## Actual offline prediction examples

| Subset | Test engine / cutoff | Point RUL | Interval lower–upper |
|---|---|---|---|
| FD001 | 3 / 126 | 60.01 | 0.00–178.73 |
| FD002 | 1 / 258 | 24.31 | 0.00–124.04 |
| FD003 | 1 / 233 | 44.19 | 0.00–187.66 |
| FD004 | 1 / 230 | 26.67 | 0.00–173.66 |

Examples contain inference output only, not labels supplied to the model. Units are operating cycles, not hours/days. Exact JSON outputs are in prediction_examples.json.

## Verification and artifacts

- Baseline parser/causal-feature tests passed before edits (10 tests). New offline experiment tests plus existing pipeline tests passed (18 tests): causal cutoffs, training-only transforms, group sample count, finite-sample quantile, held-out audit coverage, split separation, selection guardrails, artifact tampering, subset mismatch and short-history behavior.
- Every selected bundle was reloaded and checked against its in-memory predictions on all eligible official test engines (absolute tolerance1e-4). Manifest hashes, transformer/model/interval checksums and frozen selection identity are recorded.
- Existing baseline/candidate artifacts, .env and configured release pointer retained their pre-run hashes. No dataset edits, DB migration, frontend changes or live-service restart.
- Scikit-learn emitted RuntimeWarning messages about sqrt during weighted Ridge scaling of near-constant features. Candidate predictions were explicitly checked for finiteness; no nonfinite outputs were accepted. All four winners were XGBoost.
- Source: sentinel/rul_experiments.py; scripts/run_rul_improvement.py; scripts/predict_rul_experiment.py; tests/test_rul_experiments.py.
- Protocol, all candidate metrics, frozen selections, models, transformations, calibration scores, audit predictions and official-test predictions are under runs/rul-improvement-20261027. Model artifacts remain ignored; report/provenance summaries are under reports/rul-improvement-20261027.
- Experiment manifests use a separate offline schema. They cannot be silently loaded by the production Predictor. Normalization, interval metadata, routing and tenant-safe persistence require an explicit integration step before serving.

## Reproduction

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_pipeline.py tests/test_rul_experiments.py
.venv/Scripts/python.exe scripts/run_rul_improvement.py --out runs/rul-improvement-20261027
```

The runner refuses an existing output directory. Use a new version if intentionally repeating the study; do not overwrite this evidence.

Load the verified FD001 offline example:

```powershell
.venv/Scripts/python.exe scripts/predict_rul_experiment.py --bundle runs/rul-improvement-20261027/FD001 --trusted-sha256 055bc444010cd2aa4062e399f3663d1c384f2b5c29468baf5fd4f5aa08c780e8 --subset FD001 --engine 3
```

## Next decision

Point prediction improved on the frozen development gate, and independent audit results are reported separately. Uncertainty is implemented and tested but too broad to present as a precise maintenance answer. Before deployment, decide whether losing predictions before60 cycles is acceptable, evaluate a separately planned adaptive uncertainty method with genuinely held-out assessment, and explicitly integrate verified per-subset routing. Do not silently revise intervals after seeing these audit results.
