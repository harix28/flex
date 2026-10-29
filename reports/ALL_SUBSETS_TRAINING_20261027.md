# C-MAPSS four-subset training — 2026-10-27

Trained four separate subset-specific candidates using the existing pipeline. No pooling of engine identities across subsets, no automatic registration/deployment, and no overwrite of the original FD001 model.

| Subset | Selected | Train / validation / reserved engines | Test evaluated / total | MAE | RMSE | Bias | Constant MAE |
|---|---|---|---|---|---|---|---|
| FD001 | xgboost_1 | 70 / 15 / 15 | 100 / 100 | 16.14 | 21.04 | +9.18 | 35.93 |
| FD002 | ridge | 182 / 39 / 39 | 253 / 259 | 21.87 | 29.63 | -0.89 | 45.58 |
| FD003 | xgboost_1 | 70 / 15 / 15 | 100 / 100 | 22.07 | 35.38 | +13.19 | 44.09 |
| FD004 | ridge | 174 / 37 / 38 | 237 / 248 | 29.98 | 37.44 | +17.03 | 50.60 |

All error values are operating cycles, not percentages. Lower MAE/RMSE is better. Positive bias means remaining life is overestimated.

## Protocol

- Window: 30 cycles; 96 causal features (last, mean, standard deviation and slope for 3 settings + 21 sensors). No padding or interpolation.
- Seed 42; engine-disjoint 70% training / 15% validation / remaining reserved calibration groups from the training partition. Reserved calibration engines were not used.
- Compared constant, Ridge(alpha=100), XGBoost(depth=3,250 estimators) and XGBoost(depth=5,350 estimators). XGBoost learning rate .04, subsample .9, column sample .9, hist, two threads.
- Selection used engine-balanced validation RMSE across six causal cutoffs per validation engine before reading official test histories/labels. Training target is uncapped RUL; outputs clipped only at zero.
- Official test evaluation uses one final cutoff per eligible engine. Ground truth labels are evaluation-only and never model input.
- Short histories excluded: FD001=0, FD002=6, FD003=0, FD004=11. FD004 local files contain 248 test engines although the bundled readme advertises 249; results use actual validated files. No missing engine was synthesized.
- The official benchmark has now been inspected again; this is not a fresh blind benchmark and should not be reused for model-selection decisions.

## Verification

- Existing parser/feature tests: 10 passed.
- All four bundles passed artifact/schema verification. Reloaded inference matched saved predictions and independently recomputed metrics for 690 eligible test engines (absolute tolerance 1e-4).
- Short histories returned insufficient_history; each model rejected other subset IDs.
- Original runs/fd001-v1 bundle/model/report, private configuration and release pointer retained their pre-training hashes.
- No serving-code changes, database changes, release activation or raw dataset edits.

## Reproduction

Each output must be new; the trainer refuses to overwrite existing runs.

```powershell
.venv/Scripts/python.exe -m sentinel.train --data-dir data/raw --subset FD001 --out runs/fd001-20261027-candidate --window 30 --seed 42
.venv/Scripts/python.exe -m sentinel.train --data-dir data/raw --subset FD002 --out runs/fd002-20261027-candidate --window 30 --seed 42
.venv/Scripts/python.exe -m sentinel.train --data-dir data/raw --subset FD003 --out runs/fd003-20261027-candidate --window 30 --seed 42
.venv/Scripts/python.exe -m sentinel.train --data-dir data/raw --subset FD004 --out runs/fd004-20261027-candidate --window 30 --seed 42
```

Per-subset logs are in `.runtime/train-FD00X-20261027.log`; full provenance and checksums are in `reports/ALL_SUBSETS_TRAINING_20261027.json`.

## Interpretation and next step

FD001/FD003 selected XGBoost; FD002/FD004 selected Ridge because its validation RMSE was lower among the tested candidates. This does not prove Ridge is universally better. FD004 has six operating conditions and two documented degradation modes; the model still summarizes only the last 30 cycles. The benchmark alone cannot establish which factor caused each error.
FD001 rerun MAE is 16.14 versus 16.79 in the historical bundle. Splits, seed and recorded dependency versions match; this review did not isolate the source of that variation. Do not claim a methodological improvement or promote based only on this test difference.
These are experimental candidates, not a single combined model. The running dashboard continues using its existing FD001 model. Serving all four requires an explicit reviewed subset-to-bundle routing/registry change; current baseline-specific drift/evaluation defaults also require compatible reference configuration.
No calibrated uncertainty, failure probability, physical-equipment accuracy or production approval is established by these runs.
