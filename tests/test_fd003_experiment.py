import numpy as np
import pandas as pd
import pytest
from sentinel.data import read_data, split_engines, COLUMNS, VALUES
from sentinel.features import make_windows, feature_names

DATA_DIR = 'data/raw'


def test_split_disjoint():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    split = split_engines(df, seed=42)
    sets = [set(split['train']), set(split['validation']), set(split['calibration_reserved'])]
    for i, s1 in enumerate(sets):
        for j, s2 in enumerate(sets):
            if i != j:
                assert s1.isdisjoint(s2), f'Split {i} and {j} share engines'


def test_split_deterministic():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    s1 = split_engines(df, seed=42)
    s2 = split_engines(df, seed=42)
    assert s1['train'] == s2['train']
    assert s1['validation'] == s2['validation']
    assert s1['calibration_reserved'] == s2['calibration_reserved']


def test_feature_count_existing_recipe():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    X, y, _, _ = make_windows(df, window=30)
    assert X.shape[1] == 96, f'Expected 96 features, got {X.shape[1]}'
    assert list(X.columns) == feature_names()


def test_no_target_in_features():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    X, _, _, _ = make_windows(df, window=30)
    for col in X.columns:
        assert 'rul' not in col.lower()
        assert 'target' not in col.lower()


def test_no_engine_id_in_features():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    X, _, _, _ = make_windows(df, window=30)
    assert 'engine_id' not in X.columns


def test_finite_outputs():
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    X, y, _, _ = make_windows(df, window=30)
    assert np.isfinite(X.values).all()
    assert np.isfinite(y).all()


def test_warning_metrics_hand_calc():
    y_true = np.array([10, 40, 25, 60, 5])
    y_pred = np.array([35, 45, 20, 50, 35])
    
    actual_warn = y_true <= 30
    pred_warn = y_pred <= 30
    TP = int((actual_warn & pred_warn).sum())
    FP = int((~actual_warn & pred_warn).sum())
    FN = int((actual_warn & ~pred_warn).sum())
    TN = int((~actual_warn & ~pred_warn).sum())
    assert TP == 1
    assert FP == 0
    assert FN == 2
    assert TN == 2
    missed = FN / (TP + FN)
    assert abs(missed - 2/3) < 1e-9


def test_no_cross_engine_rolling():
    """Rolling features for engine 1 must not be affected by engine 2 data."""
    base = np.zeros((10, len(COLUMNS)))
    base[:, 0] = 1  # engine_id
    base[:, 1] = np.arange(1, 11)  # cycle
    extreme = np.zeros((10, len(COLUMNS)))
    extreme[:, 0] = 2
    extreme[:, 1] = np.arange(1, 11)
    extreme[:, 2:] = 999.0  # extreme sensor values for engine 2
    
    df_single = pd.DataFrame(base, columns=COLUMNS)
    df_combined = pd.DataFrame(np.vstack([base, extreme]), columns=COLUMNS)
    df_single[['engine_id', 'cycle']] = df_single[['engine_id', 'cycle']].astype(int)
    df_combined[['engine_id', 'cycle']] = df_combined[['engine_id', 'cycle']].astype(int)
    
    # Get features for engine 1 only vs engine 1 in combined dataset
    X_single, _, _, _ = make_windows(df_single, window=5)
    X_combined, _, e_ids, _ = make_windows(df_combined, window=5)
    X_eng1 = X_combined[e_ids == 1]
    
    # Engine 1 features should be identical whether engine 2 exists or not
    assert X_single.shape == X_eng1.shape
    np.testing.assert_array_almost_equal(X_single.values, X_eng1.values)


def test_causal_features():
    """Appending a future row must not change features for existing rows."""
    df = read_data(f'{DATA_DIR}/train_FD003.txt')
    engine1 = df[df.engine_id == 1].copy()
    X_base, _, _, cycles_base = make_windows(engine1, window=30, mode='train')
    
    # Add a synthetic future cycle
    last_cycle = engine1.cycle.max()
    future_row = engine1.iloc[[-1]].copy()
    future_row['cycle'] = last_cycle + 1
    engine1_extended = pd.concat([engine1, future_row], ignore_index=True)
    X_ext, _, _, cycles_ext = make_windows(engine1_extended, window=30, mode='train')
    
    # Features at same cycles must be identical
    common_cycles = set(cycles_base) & set(cycles_ext)
    for c in common_cycles:
        row_base = X_base.values[cycles_base == c]
        row_ext = X_ext.values[cycles_ext == c]
        if len(row_base) > 0 and len(row_ext) > 0:
            np.testing.assert_array_almost_equal(
                row_base[0], row_ext[0],
                err_msg=f'Features differ at cycle {c} after appending future row'
            )
