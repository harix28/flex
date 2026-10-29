from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

SUBSETS = ("FD001", "FD002", "FD003", "FD004")
SETTINGS = [f"setting_{i}" for i in range(1, 4)]
SENSORS = [f"sensor_{i:02}" for i in range(1, 22)]
VALUES = SETTINGS + SENSORS
COLUMNS = ["engine_id", "cycle"] + VALUES


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_frame(df):
    if list(df.columns) != COLUMNS or df.empty:
        raise ValueError("Expected nonempty 26-column C-MAPSS data")
    values = df.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("All readings must be finite; no missing values")
    for col in ("engine_id", "cycle"):
        a = df[col].to_numpy()
        if ((a < 1) | (a != np.floor(a))).any():
            raise ValueError(f"{col} must contain positive integers")
    if df.duplicated(["engine_id", "cycle"]).any():
        raise ValueError("Duplicate engine/cycle")
    df = df.copy().sort_values(["engine_id", "cycle"]).reset_index(drop=True)
    df[["engine_id", "cycle"]] = df[["engine_id", "cycle"]].astype(int)
    for _, group in df.groupby("engine_id"):
        if not (np.diff(group.cycle) == 1).all():
            raise ValueError("Missing cycles within engine history")
    return df


def read_data(path):
    df = pd.read_csv(path, sep=r"\s+", header=None)
    if df.shape[1] != 26:
        raise ValueError(f"Expected 26 columns, got {df.shape[1]}")
    df.columns = COLUMNS
    return validate_frame(df)


def split_engines(df, seed=42):
    ids = np.array(sorted(df.engine_id.unique()))
    if len(ids) < 10:
        raise ValueError("Need at least 10 engines for disjoint partitions")
    np.random.default_rng(seed).shuffle(ids)
    n = len(ids)
    return {"train": sorted(ids[:int(.7*n)].tolist()),
            "validation": sorted(ids[int(.7*n):int(.85*n)].tolist()),
            "calibration_reserved": sorted(ids[int(.85*n):].tolist())}
