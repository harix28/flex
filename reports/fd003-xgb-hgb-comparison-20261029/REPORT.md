# FD003 XGBoost vs HistGradientBoosting Experiment Report

**Experiment ID:** `fd003-xgb-hgb-comparison-20261029`  
**Date:** 2026-10-29  
**Scope:** Controlled reproduction and gate evaluation of NASA C-MAPSS FD003 Remaining Useful Life (RUL) regression comparing the existing Sentinel XGBoost baseline against the notebook-extracted HistGradientBoosting (HGB) recipe.

---

## 1. Important Disclaimers

> [!WARNING]
> **Untrusted Binaries Isolated:** The supplied pickle artifacts (`best_cmapss_model.pkl` and `cmapss_scaler.pkl`) were **NOT** deserialized or executed, in strict compliance with AGENTS.md Hard Rule #2. The HGB recipe was reimplemented from clean notebook source inspection (`12.ipynb`).
>
> **Benchmark Status:** The official test benchmark was previously inspected in exploratory analysis. This is a descriptive evaluation rather than a blind, held-out test. Official test labels were **never** used for fitting, feature selection, normalization, hyperparameter tuning, or model selection.

---

## 2. Dataset SHA-256 Checksums

The C-MAPSS FD003 dataset integrity was verified using SHA-256:

| File | SHA-256 Checksum | Verification Status |
|---|---|:---:|
| `data/raw/train_FD003.txt` | `2abbe9968cc5e8eb091980f51b20f62bb4127336d3482cb52071d53bf23329e2` | Verified |
| `data/raw/test_FD003.txt` | `299babd63c8d987cef079c4a425429f33b3a34797d803bbe2ad48c29dbd0d790` | Verified |
| `data/raw/RUL_FD003.txt` | `df1e0566306b174a2de41c67a3e7a51877889598b78643fc3e5685259091b7cb` | Verified |

---

## 3. Split Manifest (Seed=42, 70/15/15)

To guarantee zero cross-engine data leakage, splits are strictly engine-level (Hard Rule #6):

- **Training Engines (70 engines):**
  `[1, 2, 3, 4, 5, 6, 8, 10, 11, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 38, 39, 40, 41, 43, 44, 46, 47, 49, 51, 52, 53, 56, 57, 58, 60, 61, 62, 63, 64, 69, 70, 71, 72, 73, 74, 76, 77, 79, 80, 81, 82, 84, 85, 87, 88, 90, 92, 93, 94, 95, 96, 97, 98, 100]`
- **Validation Engines (15 engines):**
  `[7, 12, 31, 35, 45, 50, 55, 59, 68, 75, 83, 86, 89, 91, 99]`
- **Calibration Reserved Engines (15 engines):**
  `[9, 13, 14, 15, 20, 23, 36, 37, 42, 48, 54, 65, 66, 67, 78]`
- **Official Test Engines (100 engines):**
  Engines `1` through `100` (consecutive).

---

## 4. Feature Engineering Comparison

| Dimension | XGBoost Baseline Recipe | HGB Notebook Recipe |
|---|---|---|
| **Features Count** | 96 features (last, mean, std, slope across 24 columns) | 121 features (16 base + 15 diff5 + 90 rolling) |
| **Active Base Sensors** | All 21 sensors + 3 settings | 16 sensors (std > 1e-5 on train: 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 20, 21) |
| **Scaling** | None (decision trees operate on raw features) | `StandardScaler` fitted **only** on training engines |
| **Differences** | None | 5-cycle differences grouped by engine (`fillna(0.0)`) |
| **Rolling Aggregations** | None (summary statistics within trailing window) | Rolling mean & std over windows `[5, 10, 20]` (`min_periods=1, fillna(0.0)`) |
| **FD001 Dependency** | None | Sensor 10 excluded from diff & rolling due to inherited FD001 global |
| **Window Policy** | 30 cycles trailing window | Per-row with causal rolling statistics |
| **Training Target** | Uncapped True RUL | Capped at 125 cycles (`rul.clip(upper=125)`) |
| **Sample Weighting** | Engine-balanced inverse frequency | Equal per-row weighting (unweighted) |

---

## 5. Candidate Descriptions

1. **Candidate A (`candidate_a_xgb_baseline`):**
   Existing `sentinel/train.py` logic. 96-feature trailing window matrix (`window=30`), `XGBRegressor(max_depth=3, n_estimators=250, lr=0.04, subsample=0.9, colsample_bytree=0.9, random_state=42)`, uncapped target, engine-balanced sample weights.
2. **Candidate B (`candidate_b_hgb_notebook`):**
   Reimplemented notebook pipeline. 121 features, target capped at 125, `HistGradientBoostingRegressor(learning_rate=0.05, max_leaf_nodes=31, random_state=42, early_stopping=False)`. Hyperparameter `max_iter` tuned on validation MAE (best: `max_iter=250`).
3. **Candidate C (`candidate_c_xgb_notebook_features`):**
   Controlled feature/model ablation. XGBoost (`max_depth=3, n_estimators=250, lr=0.04`) trained on the same 121-feature notebook matrix with capped target (125).
4. **Candidate D (`candidate_d_hgb_sentinel_features`):**
   Controlled algorithm ablation. HGB (`learning_rate=0.05, max_leaf_nodes=31`, best: `max_iter=200`) trained on the 96-feature window matrix with uncapped target and engine-balanced weights.

---

## 6. Validation Set Metrics (Evaluated on Uncapped True RUL)

Validation evaluation used 6 fixed causal cutoffs per engine (90 windows across 15 held-out engines) to prevent temporal leakage and maintain a fair, identical evaluation distribution.

| Candidate | MAE (cycles) | RMSE (cycles) | Bias (cycles) | Near-Failure MAE | Missed Warning Rate | False Positive Rate | Gate Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Candidate A (XGB Baseline)** | **33.84** | **54.70** | -0.86 | 7.30 | **5.3% (1/19)** | 1.4% (1/71) | **BASELINE** |
| **Candidate B (HGB Notebook)** | 40.82 | 76.06 | -26.00 | 3.95 | 10.5% (2/19) | 0.0% (0/71) | **FAIL** |
| **Candidate C (XGB on 121 feats)** | 41.61 | 76.57 | -26.07 | 5.43 | 15.8% (3/19) | 0.0% (0/71) | **FAIL** |
| **Candidate D (HGB on 96 feats)** | 34.19 | 58.55 | -1.86 | 3.93 | 5.3% (1/19) | 1.4% (1/71) | **FAIL** |

### Gate Analysis

Under the predeclared frozen gate rules:
- `val_mae < baseline_val_mae` (33.84)
- `val_rmse < baseline_val_rmse` (54.70)
- `val_missed_warning_rate <= baseline_missed_warning_rate` (5.3%)
- `val_near_large_overest_pct <= baseline_near_large_overest_pct` (0.0%)

**Result:** **ZERO candidates passed the gate.**
- Candidate B failed on MAE (+6.98 cycles worse), RMSE (+21.36 cycles worse), missed warning rate (10.5% vs 5.3%), and near large overestimation (3.3% vs 0.0%).
- Candidate C failed on all criteria.
- Candidate D was closest on MAE (34.19 vs 33.84) but still higher in both MAE and RMSE.

---

## 7. Official Test Benchmark Metrics (Uncapped True RUL)

Evaluated on the final observed sequence cycle for all 100 test engines.

| Candidate | MAE (cycles) | RMSE (cycles) | Bias (cycles) | Near-Failure MAE | Missed Warning Rate | Within 20 Cycles |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Candidate A (XGB Baseline)** | 22.07 | 35.38 | +13.19 | **3.46** | **5.0% (1/20)** | 63.0% |
| **Candidate B (HGB Notebook)** | 14.07 | 19.42 | +5.06 | 6.85 | 15.0% (3/20) | 75.0% |
| **Candidate C (XGB on 121 feats)** | 14.88 | 19.74 | +5.47 | 6.56 | 20.0% (4/20) | 73.0% |
| **Candidate D (HGB on 96 feats)** | 20.91 | 34.35 | +13.15 | 3.72 | 10.0% (2/20) | 67.0% |

> [!IMPORTANT]
> **Key Insight into the Test Benchmark Disparity:**
> In the official NASA test set, Candidate B achieves lower overall MAE (14.07 vs 22.07) primarily because capping the training target at 125 clips extreme overpredictions on high-RUL healthy engines.
> However, on **safety-critical near-failure engines (actual RUL $\le$ 30 cycles)**:
> - Baseline Candidate A achieves an NF-MAE of **3.46 cycles** with only **1 missed warning (5.0%)**.
> - Candidate B degrades to an NF-MAE of **6.85 cycles** (nearly 2x worse error) and triples the missed warning rate to **15.0% (3 missed warnings out of 20)**.
> In a plant/turbofan monitoring deployment, missing impending failure is far more catastrophic than overestimating life on a brand-new engine.

---

## 8. Warning Alert Confusion Matrices (Threshold = 30 Cycles)

| Candidate | Dataset Split | TP | FP | FN | TN | Precision | Recall / Sensitivity | Missed Warning Rate |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Candidate A (XGB Baseline)** | Validation | 18 | 1 | 1 | 70 | 94.7% | 94.7% | 5.3% |
| | Official Test | 19 | 3 | 1 | 77 | 86.4% | 95.0% | 5.0% |
| **Candidate B (HGB Notebook)** | Validation | 17 | 0 | 2 | 71 | 100.0% | 89.5% | 10.5% |
| | Official Test | 17 | 2 | 3 | 78 | 89.5% | 85.0% | 15.0% |
| **Candidate C (XGB 121 Feats)** | Validation | 16 | 0 | 3 | 71 | 100.0% | 84.2% | 15.8% |
| | Official Test | 16 | 1 | 4 | 79 | 94.1% | 80.0% | 20.0% |
| **Candidate D (HGB 96 Feats)** | Validation | 18 | 1 | 1 | 70 | 94.7% | 94.7% | 5.3% |
| | Official Test | 18 | 2 | 2 | 78 | 90.0% | 90.0% | 10.0% |

---

## 9. Hyperparameter Tuning & Execution Timings

- Candidate A (XGB Baseline): 1.13s training time
- Candidate B (HGB Notebook): 10.33s total tuning/training time
  - `max_iter=100`: Val MAE = 41.49
  - `max_iter=150`: Val MAE = 41.05
  - `max_iter=200`: Val MAE = 40.88
  - `max_iter=250`: Val MAE = **40.82** (Selected)
- Candidate C (XGB 121 Feats): 2.39s training time
- Candidate D (HGB 96 Feats): 5.44s total tuning/training time
  - `max_iter=100`: Val MAE = 34.64
  - `max_iter=150`: Val MAE = 34.39
  - `max_iter=200`: Val MAE = **34.19** (Selected)
  - `max_iter=250`: Val MAE = 34.19

---

## 10. Recommendation

**DO NOT PROMOTE Candidate B to production.**

Maintain the existing **Candidate A (`candidate_a_xgb_baseline`)** recipe in `sentinel`.
Rationale:
1. Candidate B fails the predeclared validation gate on all key metrics (Val MAE, Val RMSE, Missed Warning Rate).
2. The apparent improvement on official test overall MAE is an artifact of the 125 cap on healthy engines, while actively degrading performance where it matters most: near-failure prediction accuracy (NF-MAE 3.46 vs 6.85, missed warning rate 5.0% vs 15.0%).
3. Operational safety demands minimizing missed early warnings for impending failure.

---

## 11. Exact Rerun Command

To reproduce this entire experiment from scratch:

```powershell
# Run the self-contained experiment script
.venv\Scripts\python.exe scripts\fd003_experiment.py 2>&1 | Tee-Object reports\fd003-xgb-hgb-comparison-20261029\run.log

# Run the test suite
.venv\Scripts\python.exe -m pytest tests\test_fd003_experiment.py -v
```

---

## 12. Limitations

1. **Benchmark Inspection:** The official NASA test set has been previously examined; test numbers are descriptive rather than a strict blind audit.
2. **Evaluation Truncation Mismatch:** The official test benchmark only measures the final recorded cycle per engine (where many engines are still mid-life), whereas the training distribution runs to complete failure.
3. **Uncertainty Intervals:** This experiment compared point estimators; conformal interval calibration was not attached to Candidate B.
