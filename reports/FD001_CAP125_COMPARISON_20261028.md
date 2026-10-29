# FD001 Cap-125 comparison — 2026-10-28

Decision: retain the existing offline 60-cycle candidate. The user-supplied single-row Cap-125 approach did not pass the existing validation gate. No deployment was performed. The historical dashboard model is separate and unchanged.

## Paired results

Primary target: original uncapped RUL, units operating cycles. Dense comparisons use equal weight per engine. Both models see identical evaluation engines/cutoffs.

| Evaluation | Engines | Existing MAE | Cap-125 MAE | Existing RMSE | Cap-125 RMSE |
|---|---:|---:|---:|---:|---:|
| Validation | 15 | 13.45 | 20.37 | 19.10 | 28.39 |
| Reused audit | 6 | 12.04 | 19.66 | 16.64 | 25.25 |
| Official test, >=60 cycles | 88 | 12.45 | 13.58 | 18.07 | 18.21 |

Common test ±20-cycle coverage: existing 82.95%, Cap-125 72.73%. This is a tolerance percentage, not exact classification accuracy.

Among 25 common test engines with actual RUL 1–30, mean error was 4.00 versus 11.03 cycles. Predicted RUL >30 occurred for 12% versus 32%; overestimating by >20 cycles occurred for 0% versus 20%.

Cap-125 can predict all 100 official test engines without a history-window requirement: MAE 13.31, RMSE 17.69, R² 0.8187. This availability benefit does not make an all-100 versus 88-engine comparison valid.

Secondary capped-label comparisons are in the JSON. They answer a different target question; the existing model predictions are left uncapped. On common test capped labels, Cap-125 MAE is slightly lower, but that does not reverse the uncapped or near-failure findings.

## Protocol and limitations

One candidate, with the supplied 500-tree/depth5/learning-rate0.05 settings, Cap-125 targets/prediction clipping and 30-round early stopping. It uses all training rows and cycle plus 24 settings/sensor inputs. No window features. Existing 70 training / 15 validation engines replace the pasted 80/20 split to keep engines comparable. Two threads, explicit hist method, strict canonical parser and JSON persistence are documented deviations. This is a controlled adaptation, not a verbatim Colab execution.

The baseline is runs/rul-improvement-20261027/FD001, authenticated by its previously recorded manifest. Candidate was frozen before audit/test evaluation. Audit and official benchmark were previously inspected: neither is fresh blind evidence for this follow-up. No tuning or refit followed these results. Differences bundle target capping, feature representation, training schedule and hyperparameters; this run does not isolate which change caused the result.

## Executed checks

Before changes: 18 pipeline/experiment tests passed (15.99s). After changes: the same 18 tests passed (5.55s), with no failures or skips. Actual training and paired evaluations completed. Every candidate evaluation prediction matched a JSON-reloaded model within 1e-6; data hashes, disjoint splits, test-label alignment and existing artifact/configuration hashes passed runtime checks. No full backend/frontend regression was run because application code was unchanged.

First attempt failed during evaluation with a pandas indexing KeyError for cycle; fixed by retaining index columns. Its incomplete directory was preserved. The successful v2 run used identical model parameters; no metrics-driven tuning.

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_pipeline.py tests/test_rul_experiments.py
.venv/Scripts/python.exe scripts/compare_cap125.py --out runs/fd001-cap125-20261028-v2
```

Output directory already exists; reruns must choose a new version. Protocol/source/split hashes, best iteration and full metrics are copied to the adjacent JSON report. Model and prediction CSVs remain in the ignored run directory. Source: scripts/compare_cap125.py. No pickle, dataset edits, application schema changes or model promotion.
