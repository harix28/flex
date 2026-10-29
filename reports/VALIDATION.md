# Validation evidence — 2026-10-22

Executed in Linux / Python 3.12. Not a Windows runtime certification.

- `python -m pytest -q`: **21 passed**, 2.53 s. Tests cover engine split isolation, causal features, training-serving consistency, missing history, input validation, authentication, body-size bounds, missing model, artifact tampering and manifest hash mismatch.
- Original NASA archive downloaded; all four train/test subsets passed 26-column, finite-value, duplicate and consecutive-cycle checks. See data_inventory.json and data/source.json.
- Real FD001 run: constant, Ridge and two XGBoost candidates; 70 training / 15 validation / 15 reserved calibration engines. Selected XGBoost candidate 1 using validation only. No post-test hyperparameter changes.
- Official final-window test: 100 engines, zero unavailable. MAE 16.7938509393 cycles; RMSE 21.6085044187 cycles; mean bias +9.8855211043 cycles. Constant test baseline MAE 35.9274371429, RMSE 43.4975842090 cycles.
- Loaded saved model via SHA-verified bundle and called authenticated API for all 100 test engines. Every prediction matched the saved evaluation prediction within 0.0001 cycle.
- Actual `sentinel.serve` subprocess started on loopback; HTTP `/health` and authenticated model-report endpoint passed; subprocess stopped afterward. No service is left hosted.
- Generated OpenAPI in reports/openapi.json matches this experimental API, not the broader future production contract.

Warnings observed: sklearn StandardScaler emitted a numerical sqrt warning on nearly constant Ridge features; Ridge fitting and finite metrics completed. It did not affect the selected XGBoost (unscaled input). Starlette emitted an httpx TestClient deprecation warning; all tests completed. Neither warning was hidden.

Dataset discrepancy: FD004 actual files contain **249 training / 248 test engines**; NASA archive README states 248/249. Inventory reports measured file counts rather than silently copying prose. FD004 has not been trained.

Limits: no production identity/tenant/storage tests because those modules are not implemented; no classifier/calibration/component diagnosis claims; no confidence interval or plant validation. Baseline quality is preliminary and remaining-life overestimation warrants further held-out investigation.
