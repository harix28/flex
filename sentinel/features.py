import numpy as np
import pandas as pd
from .data import VALUES

SCHEMA = "cmapss-trailing-v1"


def feature_names():
    return [f"{name}__{stat}" for stat in ("last", "mean", "std", "slope") for name in VALUES]


def window_features(values):
    a = np.asarray(values, dtype=float)
    if a.ndim != 2 or a.shape[1] != len(VALUES) or len(a) < 2 or not np.isfinite(a).all():
        raise ValueError("Invalid sensor window")
    t = np.arange(len(a), dtype=float)
    t -= t.mean()
    return np.concatenate([a[-1], a.mean(0), a.std(0), t @ a / (t @ t)])


def make_windows(df, window=30, mode="train"):
    """No future values in features. Train labels use run-to-failure end."""
    if window < 2 or mode not in ("train", "validation", "last"):
        raise ValueError("Invalid window/mode")
    rows, targets, engines, cycles = [], [], [], []
    for engine, g in df.groupby("engine_id", sort=True):
        a = g[VALUES].to_numpy()
        if len(a) < window:
            continue
        if mode == "last":
            indices = [len(a)-1]
        elif mode == "validation":
            # Fixed, evenly spaced truncations; no official test labels used.
            indices = np.unique(np.linspace(window-1, len(a)-1, 6).astype(int))
        else:
            # Bounded contribution; weights later give equal total weight per engine.
            indices = np.unique(np.linspace(window-1, len(a)-1, min(100, len(a)-window+1)).astype(int))
        for i in indices:
            rows.append(window_features(a[i-window+1:i+1]))
            cycles.append(int(g.cycle.iloc[i]))
            targets.append(int(g.cycle.iloc[-1]-g.cycle.iloc[i]))
            engines.append(int(engine))
    return (pd.DataFrame(rows, columns=feature_names()), np.asarray(targets),
            np.asarray(engines), np.asarray(cycles))
