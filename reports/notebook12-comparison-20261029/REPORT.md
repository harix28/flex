# Notebook 12 comparison — 2026-10-29

## Outcome
The reproduced notebook FD003 approach improves overall error over the existing offline FD003 candidate, but worsens error and warning misses near failure. Do not automatically promote it.

This is reproduction of the reviewed notebook recipe, NOT execution or verification of the supplied pickle binaries. The supplied pickle files were inspected statically for feature names; neither was deserialized. The exported notebook estimator is HistGradientBoostingRegressor trained on FD003, not the application's FD001 XGBoost model.

## Measured comparison
Official FD003 test data, final observed row for each of the same 94 engines, original uncapped RUL labels. Existing baseline: runs/rul-improvement-20261027/FD003, trusted manifest checked by ExperimentPredictor. Six other test engines lack its required 60-cycle history.

| Metric | Existing FD003 candidate | Notebook reproduction |
|---|---:|---:|
| MAE, cycles | 16.40 | 13.22 |
| RMSE, cycles | 25.83 | 17.90 |
| Within 20 cycles | 73.40% (69/94) | 74.47% (70/94) |
| Within 10 cycles | 51.06% (48/94) | 50.00% (47/94) |
| MAE for true RUL 1–30, 20 engines | 3.31 | 7.64 |
| Missed 30-cycle warning among those 20 | 5% (1/20) | 20% (4/20) |

Overall MAE falls approximately 19.4%. A missed warning means actual RUL <=30 while predicted RUL >30. These are benchmark observations, not operational safety guarantees or classification accuracy.

Across all 100 FD003 test engines, reproduction yields MAE 13.6243 and RMSE 18.2021 against original labels. With labels capped at 125, MAE 12.0643 and RMSE 17.2046 reproduce the notebook's displayed 12.06/17.20. Capping labels changes the question being evaluated. In results.json, common_capped leaves existing predictions unchanged and caps only labels; use common_uncapped as the primary comparison.

## Recipe and checks
- Engine-level 75/25 split with random seed 42; scaler fitted only on training engines.
- Sixteen standardized base sensors, fifteen five-cycle differences, and ninety rolling mean/std features across windows 5, 10 and 20: 121 columns.
- Sensor 10 is included as a base input but excluded from rolling features because the notebook's rolling function retains the earlier FD001 sensor selection. This dependency was reproduced deliberately.
- HistGradientBoostingRegressor: 250 iterations, learning rate 0.05, max_leaf_nodes 31, random_state 42; other parameters default.
- Training targets and predictions capped at 125.
- Assertions passed for exact ordered feature-name agreement with static model metadata, scaler input-name agreement, truncated-history feature causality at cycle 30, and test engine/label ordering.
- Training/evaluation command completed successfully and wrote results.json and common_predictions.csv. No full application test suite was run for this analysis-only task.

## Limitations and notebook findings
- Baseline and notebook training splits differ (70% versus 75% training engines). This compares the resulting recipes, not an isolated algorithm change under identical training conditions.
- The official benchmark has already been inspected; this is not a fresh blind evaluation.
- HGB automatic early stopping uses an internal row split, not an engine-grouped internal validation split. The outer held-out engines remain separate.
- Later FD002/FD004 notebook cells recompute normalization statistics from test data rather than reusing training statistics. That is unsuitable for fixed train-only preprocessing and causal replay; it is not evidence of direct target-label leakage.
- Saved notebook output reports poor FD002/FD004 transfer for this FD003 estimator. Those results were inspected, not rerun here.
- Notebook cells include a syntax error and placeholder variables; the notebook is not a clean top-to-bottom production pipeline.
- Matching rounded notebook scores does not prove the supplied binary has identical predictions.

## Files and reproduction
- results.json: actual metrics, input SHA-256 fingerprints, engine split and caveats.
- common_predictions.csv: paired predictions and labels for the 94 common engines.
- reproduce.py: reviewed recipe used for this comparison; reads local NASA data and Downloads metadata. Set its output directory to a new directory before rerunning; it intentionally refuses overwrite.

Executed from repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.venv/Scripts/python.exe .runtime/compare_notebook12.py *> .runtime/notebook12-comparison.log
```

Existing artifacts were not replaced, new model artifacts were not saved, and application code was not changed. A sensible next experiment is a shared engine split, train-only feature preprocessing, and a predeclared near-failure gate before evaluating another candidate.
