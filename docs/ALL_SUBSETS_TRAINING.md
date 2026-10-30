# All-subset cleaning, EDA and training

Offline entry point: `python -m sentinel.all_subsets_training --data-dir data/raw --out runs/<new-version>`.
Run from the repository root with its `.venv` Python. All twelve official FD001–FD004 train/test/RUL files are mandatory. The output directory must not already exist. There is no startup download, database migration or model deployment.

## Data and labels

The canonical `sentinel.data` parser enforces 26 numeric columns, finite readings, positive integer engine/cycle IDs, unique engine/cycle pairs and consecutive histories. Sorting normalizes row order. Missing values, invalid rows and duplicates cause rejection instead of silent deletion or zero filling. Valid extreme readings remain because degradation signals and operating regimes can resemble outliers. Raw files remain unchanged.

Each subset reuses the deterministic seed-42 70/15/15 engine partition. Training, validation and reserved engines stay separate. Combined-model identities include subset and engine ID, avoiding collisions across subsets. All four datasets participate, but held-out engines are deliberately not training examples.

Classifier targets reproduce the supplied external notebook's lifetime-stage definition: class 0 at <=60% elapsed lifetime, class 1 at >60% and <=80%, class 2 at >80%. These are early/middle/late simulated lifetime stages, not validated Healthy/Warning/Critical diagnoses. Future lifetime is available only to label generation. It never enters model features. Official test labels enter only after every model selection is frozen. They reconstruct total lifetime as final observed cycle plus official final RUL.

## EDA and feature engineering

Training-engine EDA includes summary quantiles, channel correlations, constant channels, IQR outlier counts, engine-life histograms, label balance and example sensor trajectories. Outlier counts are descriptive, not deletion rules. Held-out data does not drive EDA choices.

Raw features: cycle, three settings and twenty-one sensors (25 total). Engineered features: those 25 plus trailing mean and population standard deviation over up to ten cycles and five-cycle differences for all 24 settings/sensor channels (97 total). Operations group by engine and use past/current rows only. Short-history means use available observations, one-row population standard deviation is zero, and unavailable five-cycle differences are explicitly initialized to zero. No raw missing reading is imputed. Trees do not require a scaler.

Training-only selection removes constants and later columns correlated above 0.995 with an already retained column. A 64-tree ExtraTrees classifier ranks survivors by impurity importance; retain at most forty. This ranking can favor continuous/correlated features, so compare it against the raw baseline on validation rather than treating importance as causality. Selection is specific to lifetime classification; the regression experiment explicitly tests that same selected representation as an ablation.

## Training and evaluation

Five classification scopes: FD001, FD002, FD003, FD004 and pooled COMBINED. Each fits two Random Forest candidates: raw25 and engineered-selected. Parameters are 300 trees, max_depth=15, max_samples=0.4, random_state=42, n_jobs=2. Inverse-frequency engine weights give each training engine equal total weight. Choose highest validation engine-balanced macro F1. This differs from the user's unweighted full-training CSV script, so its 90.5069% is not an acceptance target.

Four separate XGBoost regression scopes test the same two feature alternatives with uncapped RUL targets. Parameters: 300 trees, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, histogram training, seed 42 and two CPU threads. Choose lowest validation engine-balanced RMSE. These are offline candidates, not replacements for the serving model and not controlled comparisons to the historical 30/60-cycle bundles.

The frozen budget is 10 RF fits, 5 feature-selector fits and 8 XGBoost fits. No official-test-driven tuning. Reports include classification accuracy, macro F1, per-class precision/recall/F1, confusion matrices, engine-balanced metrics, each subset, pooled rows and final-cycle classification. Regression reports include final-cycle and all-cycle MAE/RMSE/bias. CSVs retain subset/engine/cycle provenance. Forest class scores are uncalibrated, not failure probabilities. Repeated cycles are correlated observations, not independent engines. Benchmarks have been inspected previously, so none is described as a new blind test.

## Artifacts and verification

The run stores config, dataset checksums, exact splits, EDA, feature selection, validation results, frozen choices, test predictions and a file checksum manifest. RF models export as numeric NPZ arrays plus JSON metadata. `forest_predict(directory, X, expected_manifest_hash)` checks digests, exact feature order and finite input, then loads arrays with `allow_pickle=False`. No third-party pickle is executed. XGBoost exports native JSON. Both model families undergo prediction parity checks after reload.

The offline export is not the application's serving bundle. Integration requires a separate reviewed schema/model-loading change. The pipeline verifies that original FD001 artifact hashes and all dataset hashes remain unchanged. The `runs/` directory is ignored by Git. Never commit models, source datasets or prediction-row exports.

Tests:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_all_subsets_training.py tests/test_pipeline.py tests/test_rul_experiments.py
.venv/Scripts/python.exe -m sentinel.all_subsets_training --data-dir data/raw --out runs/all-subsets-NEW-VERSION
```

No confidence interval calibration, physical fault diagnosis, automated maintenance decisions or production promotion is part of this run. Operating-regime normalization and probability calibration remain future validation experiments.
