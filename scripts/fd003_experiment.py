"""
FD003 XGBoost vs HistGradientBoosting Experiment
Experiment ID: fd003-xgb-hgb-comparison-20261029

WARNING: Supplied pickle files (best_cmapss_model.pkl, cmapss_scaler.pkl) 
were NOT loaded. The HGB recipe was reimplemented from notebook source code only.

The official test benchmark was previously inspected. This is not a blind evaluation.
"""

import datetime
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from sentinel.data import read_data, split_engines, sha256
from sentinel.features import make_windows, feature_names


# ==============================================================================
# SECTION 1: Config and Constants
# ==============================================================================
EXPERIMENT_ID = "fd003-xgb-hgb-comparison-20261029"
DATA_DIR = Path("data/raw")
REPORTS_DIR = Path("reports") / EXPERIMENT_ID
RUNS_DIR = Path("runs") / "fd003-experiment-20261029"
SEED = 42
WINDOW_SIZE = 30
LABEL_CAP = 125

# Sensors with non-zero variance in FD003 training split
# Note: sensor_10 is active in FD003 but had near-zero variance in FD001.
# The notebook reproduced FD001 sensor selection for rolling features (excluding sensor_10).
ACTIVE_SENSORS = [
    'sensor_2', 'sensor_3', 'sensor_4', 'sensor_6', 'sensor_7',
    'sensor_8', 'sensor_9', 'sensor_10', 'sensor_11', 'sensor_12',
    'sensor_13', 'sensor_14', 'sensor_15', 'sensor_17', 'sensor_20', 'sensor_21'
]
ROLLING_SENSORS = [c for c in ACTIVE_SENSORS if c != 'sensor_10']


# ==============================================================================
# SECTION 2: Shared Utilities
# ==============================================================================
def engine_weights(engine_ids):
    """Inverse-frequency per-engine weights so each engine contributes equally."""
    engine_ids = np.asarray(engine_ids)
    _, inv, counts = np.unique(engine_ids, return_inverse=True, return_counts=True)
    w = 1.0 / counts[inv]
    return w / w.mean()


def compute_metrics(y_true, y_pred, engine_ids, label=''):
    """Compute full metric suite against UNCAPPED true RUL."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.maximum(0.0, np.asarray(y_pred, dtype=float))
    engine_ids = np.asarray(engine_ids)

    error = y_pred - y_true
    abs_error = np.abs(error)
    w = engine_weights(engine_ids)

    near = y_true <= 30
    actual_warn = y_true <= 30
    pred_warn = y_pred <= 30
    TP = int((actual_warn & pred_warn).sum())
    FP = int((~actual_warn & pred_warn).sum())
    FN = int((actual_warn & ~pred_warn).sum())  # missed warnings
    TN = int((~actual_warn & ~pred_warn).sum())

    near_w = engine_weights(engine_ids[near]) if near.any() else None

    return {
        'label': label,
        'n_windows': len(y_true),
        'n_engines': int(np.unique(engine_ids).shape[0]),
        'mae': float(np.average(abs_error, weights=w)),
        'rmse': float(np.sqrt(np.average(error**2, weights=w))),
        'bias': float(np.average(error, weights=w)),
        'within_10_pct': float(np.average(abs_error <= 10, weights=w) * 100),
        'within_20_pct': float(np.average(abs_error <= 20, weights=w) * 100),
        'over_20_pct': float(np.average(error > 20, weights=w) * 100),
        'near_failure_n': int(near.sum()),
        'near_failure_mae': float(np.average(abs_error[near], weights=near_w)) if near.any() else None,
        'near_large_overest_pct': float(np.average(error[near] > 20, weights=near_w) * 100) if near.any() else None,
        'TP': TP, 'FP': FP, 'FN': FN, 'TN': TN,
        'precision': TP / (TP + FP) if (TP + FP) > 0 else None,
        'recall': TP / (TP + FN) if (TP + FN) > 0 else None,
        'missed_warning_rate': FN / (TP + FN) if (TP + FN) > 0 else None,
        'false_positive_rate': FP / (FP + TN) if (FP + TN) > 0 else None,
    }


def to_nb_sensor_names(df):
    """Map zero-padded sensor_01..sensor_21 to sensor_1..sensor_21 for notebook compatibility."""
    mapping = {f'sensor_{i:02}': f'sensor_{i}' for i in range(1, 22)}
    return df.rename(columns=mapping)


def extract_121_features(df_nb, scaler):
    """
    Notebook recipe:
    - 16 base active sensors scaled with StandardScaler
    - 15 5-cycle differences (grouped by engine, fillna(0))
    - 90 rolling means and stds for windows 5, 10, 20 (min_periods=1, fillna(0))
    Total: 121 features.
    """
    x_scaled = pd.DataFrame(scaler.transform(df_nb[ACTIVE_SENSORS]), columns=ACTIVE_SENSORS, index=df_nb.index)
    temp = x_scaled.copy()
    temp['engine_id'] = df_nb['engine_id'].values

    grouped = temp.groupby('engine_id', sort=False)[ROLLING_SENSORS]
    delta_5 = grouped.diff(5).fillna(0.0).add_suffix('_delta_5')

    blocks = [x_scaled, delta_5]
    for w in [5, 10, 20]:
        r_mean = grouped.rolling(w, min_periods=1).mean().reset_index(level=0, drop=True).add_suffix(f'_mean_{w}')
        r_std = grouped.rolling(w, min_periods=1).std().fillna(0.0).reset_index(level=0, drop=True).add_suffix(f'_std_{w}')
        blocks.extend([r_mean, r_std])

    return pd.concat(blocks, axis=1).astype(np.float32)


# ==============================================================================
# SECTION 6: Gate Check Utility
# ==============================================================================
def apply_gate(baseline_metrics, candidate_metrics):
    """
    A candidate QUALIFIES only if ALL conditions met:
    - val_mae < baseline val_mae
    - val_rmse < baseline val_rmse  
    - val_missed_warning_rate <= baseline val_missed_warning_rate
    - val_near_large_overest_pct <= baseline val_near_large_overest_pct
    Gate is NOT relaxed even if results are disappointing.
    """
    b_miss = baseline_metrics['missed_warning_rate'] if baseline_metrics['missed_warning_rate'] is not None else 1.0
    c_miss = candidate_metrics['missed_warning_rate'] if candidate_metrics['missed_warning_rate'] is not None else 1.0

    b_over = baseline_metrics['near_large_overest_pct'] if baseline_metrics['near_large_overest_pct'] is not None else 100.0
    c_over = candidate_metrics['near_large_overest_pct'] if candidate_metrics['near_large_overest_pct'] is not None else 100.0

    passes = (
        candidate_metrics['mae'] < baseline_metrics['mae'] and
        candidate_metrics['rmse'] < baseline_metrics['rmse'] and
        c_miss <= b_miss and
        c_over <= b_over
    )
    return bool(passes)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    print("=" * 80)
    print("FD003 XGBoost vs HistGradientBoosting Experiment")
    print(f"Experiment ID: {EXPERIMENT_ID}")
    print("=" * 80)
    print("WARNING: Supplied pickle files were NOT loaded. Reimplemented from notebook source.")
    print("WARNING: Official test benchmark was previously inspected. Not a blind evaluation.\n")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    train_path = DATA_DIR / "train_FD003.txt"
    test_path = DATA_DIR / "test_FD003.txt"
    rul_path = DATA_DIR / "RUL_FD003.txt"

    train_df = read_data(train_path)
    test_df = read_data(test_path)
    test_truth = np.loadtxt(rul_path, ndmin=1)

    # 2. Canonical Split
    split = split_engines(train_df, seed=SEED)
    train_engines = split['train']
    val_engines = split['validation']

    tr_df = train_df[train_df.engine_id.isin(train_engines)].copy()
    va_df = train_df[train_df.engine_id.isin(val_engines)].copy()

    print(f"Data Split: {len(train_engines)} Train Engines | {len(val_engines)} Val Engines | {len(split['calibration_reserved'])} Calibration Reserved")
    print(f"Official Test: {test_df.engine_id.nunique()} Engines, Ground Truth shape: {test_truth.shape}\n")

    # 3. Prepare 96-feature matrices (Sentinel window recipe)
    print("Extracting 96-feature trailing window representations...")
    t0 = time.time()
    X_tr_96, y_tr_96, ids_tr_96, cycles_tr_96 = make_windows(tr_df, window=WINDOW_SIZE, mode='train')
    X_va_96, y_va_96, ids_va_96, cycles_va_96 = make_windows(va_df, window=WINDOW_SIZE, mode='validation')
    X_te_96, _, ids_te_96, cycles_te_96 = make_windows(test_df, window=WINDOW_SIZE, mode='last')
    print(f"96-feature extraction complete in {time.time() - t0:.2f}s: Train={X_tr_96.shape}, Val={X_va_96.shape}, Test={X_te_96.shape}")

    w_tr_96 = engine_weights(ids_tr_96)
    y_te_true = test_truth[ids_te_96 - 1]

    # 4. Prepare 121-feature matrices (Notebook recipe)
    print("Extracting 121-feature notebook representations...")
    t0 = time.time()
    tr_df_nb = to_nb_sensor_names(tr_df)
    va_df_nb = to_nb_sensor_names(va_df)
    te_df_nb = to_nb_sensor_names(test_df)

    scaler_121 = StandardScaler().fit(tr_df_nb[ACTIVE_SENSORS])

    X_tr_121 = extract_121_features(tr_df_nb, scaler_121)
    y_tr_121_uncapped = (tr_df.groupby('engine_id')['cycle'].transform('max') - tr_df['cycle']).values
    y_tr_121_capped = np.clip(y_tr_121_uncapped, 0, LABEL_CAP)
    ids_tr_121 = tr_df['engine_id'].values

    # Validation cutoffs: exact same 6 causal cutoffs per engine
    X_va_121_all = extract_121_features(va_df_nb, scaler_121)
    va_121_rows, va_121_y, va_121_ids, va_121_cycles = [], [], [], []
    for eid, group in va_df.groupby('engine_id', sort=True):
        indices = np.unique(np.linspace(WINDOW_SIZE - 1, len(group) - 1, 6).astype(int))
        group_fe = X_va_121_all.loc[group.index]
        va_121_rows.append(group_fe.iloc[indices])
        va_121_y.extend((group.cycle.iloc[-1] - group.cycle.iloc[indices]).tolist())
        va_121_ids.extend([eid] * len(indices))
        va_121_cycles.extend(group.cycle.iloc[indices].tolist())

    X_va_121 = pd.concat(va_121_rows, axis=0)
    y_va_121 = np.asarray(va_121_y, dtype=float)
    ids_va_121 = np.asarray(va_121_ids, dtype=int)
    cycles_va_121 = np.asarray(va_121_cycles, dtype=int)

    # Test cutoffs: final observed cycle (tail 1) per test engine
    X_te_121_all = extract_121_features(te_df_nb, scaler_121)
    last_idx_te = te_df_nb.groupby('engine_id').tail(1).sort_values('engine_id').index
    X_te_121 = X_te_121_all.loc[last_idx_te]
    ids_te_121 = te_df_nb.loc[last_idx_te, 'engine_id'].values
    cycles_te_121 = te_df_nb.loc[last_idx_te, 'cycle'].values
    y_te_121_true = test_truth[ids_te_121 - 1]

    # Verify alignment between 96 and 121 validation targets
    assert np.array_equal(y_va_96, y_va_121), "Validation target mismatch between feature sets!"
    assert np.array_equal(ids_va_96, ids_va_121), "Validation engine ID mismatch between feature sets!"
    assert np.array_equal(ids_te_96, ids_te_121), "Test engine ID mismatch between feature sets!"
    assert np.array_equal(y_te_true, y_te_121_true), "Test ground truth mismatch between feature sets!"
    print(f"121-feature extraction complete in {time.time() - t0:.2f}s: Train={X_tr_121.shape}, Val={X_va_121.shape}, Test={X_te_121.shape}\n")

    val_metrics = {}
    test_metrics = {}
    trained_models = {}
    val_predictions = {}
    test_predictions = {}
    timings = {}
    tuning_info = {}

    # ==========================================================================
    # CANDIDATE A: Baseline XGBoost (96 features, uncapped target, engine weights)
    # ==========================================================================
    print("--- Training Candidate A: XGBoost Baseline (96 features, uncapped) ---")
    t0 = time.time()
    xgb_a = XGBRegressor(
        max_depth=3,
        n_estimators=250,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.9,
        objective='reg:squarederror',
        tree_method='hist',
        n_jobs=2,
        random_state=SEED
    )
    xgb_a.fit(X_tr_96, y_tr_96, sample_weight=w_tr_96)
    timings['candidate_a_xgb_baseline'] = time.time() - t0

    pred_va_a = np.maximum(0.0, xgb_a.predict(X_va_96))
    pred_te_a = np.maximum(0.0, xgb_a.predict(X_te_96))

    val_metrics['candidate_a_xgb_baseline'] = compute_metrics(y_va_96, pred_va_a, ids_va_96, label='Val - Cand A')
    test_metrics['candidate_a_xgb_baseline'] = compute_metrics(y_te_true, pred_te_a, ids_te_96, label='Test - Cand A')
    trained_models['candidate_a_xgb_baseline'] = ('xgboost', xgb_a)
    val_predictions['candidate_a_xgb_baseline'] = (ids_va_96, cycles_va_96, y_va_96, pred_va_a)
    test_predictions['candidate_a_xgb_baseline'] = (ids_te_96, cycles_te_96, y_te_true, pred_te_a)
    print(f"Candidate A trained in {timings['candidate_a_xgb_baseline']:.2f}s | Val MAE: {val_metrics['candidate_a_xgb_baseline']['mae']:.2f}\n")

    # ==========================================================================
    # CANDIDATE B: HGB Notebook Recipe (121 features, capped target at 125)
    # ==========================================================================
    print("--- Tuning & Training Candidate B: HGB Notebook Recipe (121 features, capped 125) ---")
    best_hgb_b = None
    best_iter_b = None
    best_val_mae_b = float('inf')
    tuning_log_b = {}

    t0 = time.time()
    for n_iter in [100, 150, 200, 250]:
        hgb = HistGradientBoostingRegressor(
            max_iter=n_iter,
            learning_rate=0.05,
            max_leaf_nodes=31,
            random_state=SEED,
            early_stopping=False
        )
        hgb.fit(X_tr_121, y_tr_121_capped)
        pred_val = np.clip(hgb.predict(X_va_121), 0.0, LABEL_CAP)
        m = compute_metrics(y_va_121, pred_val, ids_va_121)
        tuning_log_b[n_iter] = m['mae']
        print(f"  Candidate B max_iter={n_iter}: Val MAE = {m['mae']:.2f}, Val RMSE = {m['rmse']:.2f}")
        if m['mae'] < best_val_mae_b:
            best_val_mae_b = m['mae']
            best_hgb_b = hgb
            best_iter_b = n_iter

    timings['candidate_b_hgb_notebook'] = time.time() - t0
    tuning_info['candidate_b_hgb_notebook'] = {'chosen_max_iter': best_iter_b, 'tuning_evaluations': tuning_log_b}
    print(f"Candidate B selected max_iter={best_iter_b} (Val MAE: {best_val_mae_b:.2f}) in {timings['candidate_b_hgb_notebook']:.2f}s")

    pred_va_b = np.clip(best_hgb_b.predict(X_va_121), 0.0, LABEL_CAP)
    pred_te_b = np.clip(best_hgb_b.predict(X_te_121), 0.0, LABEL_CAP)

    val_metrics['candidate_b_hgb_notebook'] = compute_metrics(y_va_121, pred_va_b, ids_va_121, label='Val - Cand B')
    test_metrics['candidate_b_hgb_notebook'] = compute_metrics(y_te_121_true, pred_te_b, ids_te_121, label='Test - Cand B')
    trained_models['candidate_b_hgb_notebook'] = ('hgb', best_hgb_b)
    val_predictions['candidate_b_hgb_notebook'] = (ids_va_121, cycles_va_121, y_va_121, pred_va_b)
    test_predictions['candidate_b_hgb_notebook'] = (ids_te_121, cycles_te_121, y_te_121_true, pred_te_b)
    print()

    # ==========================================================================
    # CANDIDATE C: XGBoost on 121 Features (Controlled Ablation: same features & cap)
    # ==========================================================================
    print("--- Training Candidate C: XGBoost on 121 Features (capped 125) ---")
    t0 = time.time()
    xgb_c = XGBRegressor(
        max_depth=3,
        n_estimators=250,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.9,
        objective='reg:squarederror',
        tree_method='hist',
        n_jobs=2,
        random_state=SEED
    )
    xgb_c.fit(X_tr_121, y_tr_121_capped)
    timings['candidate_c_xgb_notebook_features'] = time.time() - t0

    pred_va_c = np.clip(xgb_c.predict(X_va_121), 0.0, LABEL_CAP)
    pred_te_c = np.clip(xgb_c.predict(X_te_121), 0.0, LABEL_CAP)

    val_metrics['candidate_c_xgb_notebook_features'] = compute_metrics(y_va_121, pred_va_c, ids_va_121, label='Val - Cand C')
    test_metrics['candidate_c_xgb_notebook_features'] = compute_metrics(y_te_121_true, pred_te_c, ids_te_121, label='Test - Cand C')
    trained_models['candidate_c_xgb_notebook_features'] = ('xgboost', xgb_c)
    val_predictions['candidate_c_xgb_notebook_features'] = (ids_va_121, cycles_va_121, y_va_121, pred_va_c)
    test_predictions['candidate_c_xgb_notebook_features'] = (ids_te_121, cycles_te_121, y_te_121_true, pred_te_c)
    print(f"Candidate C trained in {timings['candidate_c_xgb_notebook_features']:.2f}s | Val MAE: {val_metrics['candidate_c_xgb_notebook_features']['mae']:.2f}\n")

    # ==========================================================================
    # CANDIDATE D: HGB on 96 Features (Controlled Ablation: same as A, HGB model)
    # ==========================================================================
    print("--- Tuning & Training Candidate D: HGB on 96 Features (uncapped, engine weights) ---")
    best_hgb_d = None
    best_iter_d = None
    best_val_mae_d = float('inf')
    tuning_log_d = {}

    t0 = time.time()
    for n_iter in [100, 150, 200, 250]:
        hgb = HistGradientBoostingRegressor(
            max_iter=n_iter,
            learning_rate=0.05,
            max_leaf_nodes=31,
            random_state=SEED,
            early_stopping=False
        )
        hgb.fit(X_tr_96, y_tr_96, sample_weight=w_tr_96)
        pred_val = np.maximum(0.0, hgb.predict(X_va_96))
        m = compute_metrics(y_va_96, pred_val, ids_va_96)
        tuning_log_d[n_iter] = m['mae']
        print(f"  Candidate D max_iter={n_iter}: Val MAE = {m['mae']:.2f}, Val RMSE = {m['rmse']:.2f}")
        if m['mae'] < best_val_mae_d:
            best_val_mae_d = m['mae']
            best_hgb_d = hgb
            best_iter_d = n_iter

    timings['candidate_d_hgb_sentinel_features'] = time.time() - t0
    tuning_info['candidate_d_hgb_sentinel_features'] = {'chosen_max_iter': best_iter_d, 'tuning_evaluations': tuning_log_d}
    print(f"Candidate D selected max_iter={best_iter_d} (Val MAE: {best_val_mae_d:.2f}) in {timings['candidate_d_hgb_sentinel_features']:.2f}s")

    pred_va_d = np.maximum(0.0, best_hgb_d.predict(X_va_96))
    pred_te_d = np.maximum(0.0, best_hgb_d.predict(X_te_96))

    val_metrics['candidate_d_hgb_sentinel_features'] = compute_metrics(y_va_96, pred_va_d, ids_va_96, label='Val - Cand D')
    test_metrics['candidate_d_hgb_sentinel_features'] = compute_metrics(y_te_true, pred_te_d, ids_te_96, label='Test - Cand D')
    trained_models['candidate_d_hgb_sentinel_features'] = ('hgb', best_hgb_d)
    val_predictions['candidate_d_hgb_sentinel_features'] = (ids_va_96, cycles_va_96, y_va_96, pred_va_d)
    test_predictions['candidate_d_hgb_sentinel_features'] = (ids_te_96, cycles_te_96, y_te_true, pred_te_d)
    print()

    # ==========================================================================
    # SECTION 6: Gate Check Evaluation
    # ==========================================================================
    baseline_val = val_metrics['candidate_a_xgb_baseline']
    gate_results = {}
    for name, m in val_metrics.items():
        if name == 'candidate_a_xgb_baseline':
            gate_results[name] = True  # Baseline is self-referential
        else:
            gate_results[name] = apply_gate(baseline_val, m)

    # ==========================================================================
    # SECTION 7: Save Artifacts
    # ==========================================================================
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    feature_schemas = {
        'candidate_a_xgb_baseline': feature_names(),
        'candidate_b_hgb_notebook': list(X_tr_121.columns),
        'candidate_c_xgb_notebook_features': list(X_tr_121.columns),
        'candidate_d_hgb_sentinel_features': feature_names(),
    }

    for name in val_metrics.keys():
        cand_dir = RUNS_DIR / name
        cand_dir.mkdir(parents=True, exist_ok=True)
        m_type, model_obj = trained_models[name]

        # Model file
        if m_type == 'xgboost':
            model_obj.save_model(str(cand_dir / 'model.json'))
        else:
            # HGB cannot be serialized with save_model; save param manifest
            hgb_payload = {
                'model_type': 'HistGradientBoostingRegressor',
                'params': {k: v for k, v in model_obj.get_params().items() if not callable(v)},
                'n_iter_': int(model_obj.n_iter_),
                'tuning': tuning_info.get(name, {})
            }
            (cand_dir / 'model.json').write_text(json.dumps(hgb_payload, indent=2))

        # Feature schema
        feats = feature_schemas[name]
        (cand_dir / 'feature_schema.json').write_text(json.dumps({
            'candidate_id': name,
            'n_features': len(feats),
            'feature_names': feats
        }, indent=2))

        # Preprocessing
        if name in ('candidate_b_hgb_notebook', 'candidate_c_xgb_notebook_features'):
            prep_payload = {
                'mode': 'StandardScaler',
                'fitted_on': 'train_engines_only',
                'active_sensors': ACTIVE_SENSORS,
                'rolling_sensors': ROLLING_SENSORS,
                'mean_': scaler_121.mean_.tolist(),
                'scale_': scaler_121.scale_.tolist()
            }
        else:
            prep_payload = {
                'mode': 'raw_unscaled',
                'description': 'Tree models operate on raw summary features directly without StandardScaler'
            }
        (cand_dir / 'preprocessing.json').write_text(json.dumps(prep_payload, indent=2))

        # Metrics
        (cand_dir / 'metrics_validation.json').write_text(json.dumps(val_metrics[name], indent=2))
        (cand_dir / 'metrics_test.json').write_text(json.dumps(test_metrics[name], indent=2))

        # Predictions CSVs
        v_ids, v_cycs, v_true, v_pred = val_predictions[name]
        pd.DataFrame({
            'engine_id': v_ids,
            'cycle': v_cycs,
            'true_rul_uncapped': v_true,
            'predicted_rul': v_pred
        }).to_csv(cand_dir / 'predictions_validation.csv', index=False)

        t_ids, t_cycs, t_true, t_pred = test_predictions[name]
        pd.DataFrame({
            'engine_id': t_ids,
            'cycle': t_cycs,
            'true_rul_uncapped': t_true,
            'predicted_rul': t_pred
        }).to_csv(cand_dir / 'predictions_test.csv', index=False)

        # Candidate Manifest
        manifest = {
            'candidate_id': name,
            'model_type': m_type,
            'n_features': len(feats),
            'gate_passed': gate_results[name],
            'training_time_seconds': timings[name],
            'created_at': now_iso,
            'tuning': tuning_info.get(name, None)
        }
        (cand_dir / 'candidate_manifest.json').write_text(json.dumps(manifest, indent=2))

    # Save summary report in REPORTS_DIR
    summary_report = {
        'experiment_id': EXPERIMENT_ID,
        'created_at': now_iso,
        'dataset': 'FD003',
        'validation_metrics': val_metrics,
        'test_metrics': test_metrics,
        'gate_results': gate_results,
        'timings_seconds': timings,
        'tuning_info': tuning_info
    }
    (REPORTS_DIR / 'results.json').write_text(json.dumps(summary_report, indent=2))

    # ==========================================================================
    # SECTION 9: Print Summary Tables
    # ==========================================================================
    print("=" * 85)
    print("VALIDATION METRICS (Evaluated against UNCAPPED True RUL, 6 Cutoffs per Engine)")
    print("=" * 85)
    print(f"{'Candidate':<35} {'MAE':>7} {'RMSE':>7} {'Bias':>7} {'NF-MAE':>7} {'Miss%':>7} {'Gate':>6}")
    print("-" * 85)
    for name, m in val_metrics.items():
        gate_str = 'BASE' if name == 'candidate_a_xgb_baseline' else ('PASS' if gate_results[name] else 'FAIL')
        miss_str = f"{m['missed_warning_rate']*100:.1f}%" if m['missed_warning_rate'] is not None else "N/A"
        nf_mae_str = f"{m['near_failure_mae']:.2f}" if m['near_failure_mae'] is not None else "N/A"
        print(f"{name:<35} {m['mae']:>7.2f} {m['rmse']:>7.2f} {m['bias']:>7.2f} {nf_mae_str:>7} {miss_str:>7} {gate_str:>6}")

    print("\n" + "=" * 85)
    print("OFFICIAL TEST METRICS (Evaluated against UNCAPPED True RUL, Last Observed Cycle)")
    print("NOTE: Official test labels were previously inspected. Descriptive evaluation only.")
    print("=" * 85)
    print(f"{'Candidate':<35} {'MAE':>7} {'RMSE':>7} {'Bias':>7} {'NF-MAE':>7} {'Miss%':>7} {'<20%':>7}")
    print("-" * 85)
    for name, m in test_metrics.items():
        miss_str = f"{m['missed_warning_rate']*100:.1f}%" if m['missed_warning_rate'] is not None else "N/A"
        nf_mae_str = f"{m['near_failure_mae']:.2f}" if m['near_failure_mae'] is not None else "N/A"
        w20_str = f"{m['within_20_pct']:.1f}%"
        print(f"{name:<35} {m['mae']:>7.2f} {m['rmse']:>7.2f} {m['bias']:>7.2f} {nf_mae_str:>7} {miss_str:>7} {w20_str:>7}")

    print("\n" + "=" * 85)
    print("WARNING ALERT CONFUSION MATRIX (Near-Failure Threshold = 30 Cycles)")
    print("=" * 85)
    print(f"{'Candidate':<35} {'Split':<6} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'Precision':>10} {'Recall':>8}")
    print("-" * 85)
    for name in val_metrics.keys():
        vm = val_metrics[name]
        v_p = f"{vm['precision']*100:.1f}%" if vm['precision'] is not None else "N/A"
        v_r = f"{vm['recall']*100:.1f}%" if vm['recall'] is not None else "N/A"
        print(f"{name:<35} {'Val':<6} {vm['TP']:>4} {vm['FP']:>4} {vm['FN']:>4} {vm['TN']:>4} {v_p:>10} {v_r:>8}")

        tm = test_metrics[name]
        t_p = f"{tm['precision']*100:.1f}%" if tm['precision'] is not None else "N/A"
        t_r = f"{tm['recall']*100:.1f}%" if tm['recall'] is not None else "N/A"
        print(f"{name:<35} {'Test':<6} {tm['TP']:>4} {tm['FP']:>4} {tm['FN']:>4} {tm['TN']:>4} {t_p:>10} {t_r:>8}")

    print("\n" + "=" * 85)
    print("GATE SUMMARY AND RECOMMENDATION")
    print("=" * 85)
    qualified = [name for name, passed in gate_results.items() if passed and name != 'candidate_a_xgb_baseline']
    if qualified:
        print(f"Qualified candidates: {', '.join(qualified)}")
    else:
        print("NO candidate satisfied ALL gate conditions against the baseline.")
        print(f"Baseline (Candidate A): Val MAE={baseline_val['mae']:.2f}, Val RMSE={baseline_val['rmse']:.2f}, Val Miss%={(baseline_val['missed_warning_rate'] or 0)*100:.1f}%")
        for name in [k for k in val_metrics if k != 'candidate_a_xgb_baseline']:
            m = val_metrics[name]
            miss_rate = (m['missed_warning_rate'] or 0) * 100
            print(f"  {name}: Val MAE={m['mae']:.2f}, Val RMSE={m['rmse']:.2f}, Val Miss%={miss_rate:.1f}% -> Gate: FAIL")
    print("=" * 85)


if __name__ == '__main__':
    main()
