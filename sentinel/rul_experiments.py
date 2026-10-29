"""Offline causal RUL experiments and engine-group uncertainty; no serving integration."""
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
from sentinel.data import VALUES, SETTINGS, SENSORS, COLUMNS, validate_frame, sha256
from sentinel.features import feature_names, window_features
from sentinel.train import weights

MIN_CUTOFF = 60
SCHEMA = 'cmapss-rul-experiment-v1'


def fit_transform(frame, normalized=False):
    """Caller must supply training engines only. Store numeric parameters, never pickle."""
    if not normalized:
        return {'mode': 'raw', 'training_engine_ids': sorted(map(int, frame.engine_id.unique()))}
    settings = frame[SETTINGS].to_numpy(float)
    center, scale = settings.mean(0), settings.std(0)
    scale[scale < 1e-8] = 1
    clusters = KMeans(n_clusters=6, random_state=42, n_init=10).fit((settings-center)/scale)
    sensor = frame[SENSORS].to_numpy(float)
    means, scales = [], []
    for index in range(6):
        group = sensor[clusters.labels_ == index]
        deviation = group.std(0)
        deviation[deviation < 1e-8] = 1
        means.append(group.mean(0).tolist()); scales.append(deviation.tolist())
    return {'mode': 'condition_normalized', 'settings_center': center.tolist(),
            'settings_scale': scale.tolist(), 'centers': clusters.cluster_centers_.tolist(),
            'sensor_means': means, 'sensor_scales': scales,
            'training_engine_ids': sorted(map(int, frame.engine_id.unique()))}


def transform_frame(frame, transform):
    if transform['mode'] == 'raw':
        return frame.copy()
    z = (frame[SETTINGS].to_numpy(float)-np.array(transform['settings_center']))/np.array(transform['settings_scale'])
    distances = ((z[:, None, :] - np.array(transform['centers'])[None, :, :])**2).sum(2)
    labels = distances.argmin(1)
    result = frame.copy()
    result[SENSORS] = (frame[SENSORS].to_numpy(float)-np.array(transform['sensor_means'])[labels])/np.array(transform['sensor_scales'])[labels]
    return result


def windows(frame, window, transform, mode='dense', min_cutoff=MIN_CUTOFF):
    if mode not in ('dense', 'train', 'last') or window < 2:
        raise ValueError('Invalid window mode')
    transformed = transform_frame(frame, transform)
    features, targets, engines, cutoffs = [], [], [], []
    for engine, group in transformed.groupby('engine_id', sort=True):
        values = group[VALUES].to_numpy(float)
        eligible = np.flatnonzero((group.cycle.to_numpy() >= min_cutoff) & (np.arange(len(group)) >= window-1))
        if not len(eligible):
            continue
        if mode == 'train':
            eligible = eligible[np.unique(np.linspace(0, len(eligible)-1, min(100, len(eligible))).astype(int))]
        elif mode == 'last':
            eligible = eligible[-1:]
        for end in eligible:
            features.append(window_features(values[end-window+1:end+1]))
            targets.append(int(group.cycle.iloc[-1]-group.cycle.iloc[end]))
            engines.append(int(engine)); cutoffs.append(int(group.cycle.iloc[end]))
    return np.asarray(features, dtype=float).reshape(-1, 96), np.asarray(targets), np.asarray(engines), np.asarray(cutoffs)


class PointModel:
    def __init__(self, family, model):
        self.family, self.model = family, model

    def predict(self, features):
        if not len(features):
            return np.array([], dtype=float)
        if self.family == 'xgboost':
            values = self.model.predict(pd.DataFrame(features, columns=feature_names()))
        elif self.family == 'ridge':
            m = self.model
            values = ((features-np.array(m['mean']))/np.array(m['scale'])) @ np.array(m['coef'])+m['intercept']
        elif self.family == 'constant':
            values = np.full(len(features), self.model['constant'])
        else:
            raise ValueError('Unsupported model family')
        if not np.isfinite(values).all():
            raise ValueError('Nonfinite model output')
        return np.maximum(0, values)

    def save(self, path):
        if self.family == 'xgboost':
            self.model.save_model(path)
        else:
            Path(path).write_text(json.dumps(self.model), encoding='utf-8')

    @classmethod
    def load(cls, path, family):
        if family == 'xgboost':
            model = XGBRegressor(); model.load_model(path)
        else:
            model = json.loads(Path(path).read_text())
        return cls(family, model)


def fit_model(features, targets, engines, family):
    sample_weights = weights(engines)
    if family == 'ridge':
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler().fit(features, sample_weight=sample_weights)
        model = Ridge(alpha=100).fit(scaler.transform(features), targets, sample_weight=sample_weights)
        return PointModel('ridge', {'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(),
            'coef': model.coef_.tolist(), 'intercept': float(model.intercept_)})
    depth, count = (3, 250) if family == 'xgboost_1' else (5, 350)
    if family not in ('xgboost_1', 'xgboost_2'):
        raise ValueError('Unsupported fit candidate')
    model = XGBRegressor(max_depth=depth, n_estimators=count, learning_rate=.04, subsample=.9,
        colsample_bytree=.9, objective='reg:squarederror', tree_method='hist', n_jobs=2, random_state=42)
    model.fit(pd.DataFrame(features, columns=feature_names()), targets, sample_weight=sample_weights)
    return PointModel('xgboost', model)


def scores(targets, predictions, engines):
    if not len(targets):
        return {'status': 'no_samples', 'windows': 0, 'engines': 0}
    error = predictions-targets
    w = weights(engines)
    result = {'status': 'available', 'windows': len(targets), 'engines': len(np.unique(engines)),
        'mae': float(np.average(abs(error), weights=w)),
        'rmse': float(np.sqrt(np.average(error**2, weights=w))),
        'bias': float(np.average(error, weights=w)),
        'within20_percent': float(np.average(abs(error)<=20, weights=w)*100),
        'within10_percent': float(np.average(abs(error)<=10, weights=w)*100),
        'over20_percent': float(np.average(error>20, weights=w)*100)}
    near = (targets > 0) & (targets <= 30)
    if near.any():
        nw = weights(engines[near])
        result.update(near_windows=int(near.sum()), near_engines=len(np.unique(engines[near])),
            near_miss_percent=float(np.average(predictions[near]>30, weights=nw)*100),
            near_over20_percent=float(np.average(error[near]>20, weights=nw)*100),
            near_mae=float(np.average(abs(error[near]), weights=nw)))
    else:
        result.update(near_windows=0, near_engines=0, near_miss_percent=None, near_over20_percent=None, near_mae=None)
    return result


def qualifies(candidate, baseline):
    """Frozen development gate, not an operational safety certification."""
    return (candidate['mae'] < baseline['mae'] and candidate['rmse'] < baseline['rmse']
        and candidate['within20_percent'] >= baseline['within20_percent']
        and candidate['over20_percent'] <= baseline['over20_percent']
        and candidate['near_miss_percent'] is not None
        and candidate['near_miss_percent'] <= baseline['near_miss_percent']
        and candidate['near_over20_percent'] <= baseline['near_over20_percent'])


def split_reserved(ids, seed=43):
    ids = np.array(sorted(ids), dtype=int)
    if len(ids) < 10 or len(np.unique(ids)) != len(ids):
        raise ValueError('Need at least ten distinct reserved engines')
    np.random.default_rng(seed).shuffle(ids)
    count = max(9, math.ceil(.6*len(ids)))
    return sorted(map(int, ids[:count])), sorted(map(int, ids[count:]))


def calibrate(targets, predictions, engines, alpha=.1):
    """One max residual per engine, not thousands of pseudo-independent windows."""
    if not 0 < alpha < 1 or not len(targets) or len(targets) != len(predictions) or len(targets) != len(engines):
        raise ValueError('Invalid calibration arrays')
    residuals = np.abs(np.asarray(predictions)-np.asarray(targets))
    if not np.isfinite(residuals).all():
        raise ValueError('Nonfinite calibration scores')
    unique = np.unique(engines)
    group_scores = [float(residuals[engines == engine].max()) for engine in unique]
    rank = math.ceil((len(unique)+1)*(1-alpha))
    radius = sorted(group_scores)[rank-1] if rank <= len(group_scores) else None
    return {'method': 'engine_max_absolute_residual_split_conformal', 'alpha': alpha,
        'nominal_coverage': 1-alpha, 'min_cutoff': MIN_CUTOFF, 'calibration_engine_ids': list(map(int, unique)),
        'calibration_engine_count': len(unique), 'order_statistic_rank': rank,
        'radius_cycles': radius, 'status': 'available' if radius is not None else 'insufficient_calibration_engines',
        'engine_scores': dict(zip(map(str, unique), group_scores)),
        'assumption': 'Exchangeable engines and matching trajectory/cutoff distribution; no guarantee under drift or official-test truncation shift.'}


def interval_audit(targets, predictions, engines, calibration):
    radius = calibration['radius_cycles']
    if radius is None or not len(targets):
        return {'status': 'unavailable', 'engines': len(np.unique(engines))}
    lower, upper = np.maximum(0, predictions-radius), predictions+radius
    covered = (targets >= lower) & (targets <= upper)
    unique = np.unique(engines)
    w = weights(engines)
    return {'status': 'available', 'windows': len(targets), 'engines': len(unique),
        'engine_simultaneous_coverage_percent': float(np.mean([covered[engines==engine].all() for engine in unique])*100),
        'engine_balanced_window_coverage_percent': float(np.average(covered, weights=w)*100),
        'mean_width_cycles': float(np.average(upper-lower, weights=w)),
        'median_width_cycles': float(np.median(upper-lower)),
        'near_failure_window_coverage_percent': float(covered[(targets>0)&(targets<=30)].mean()*100) if ((targets>0)&(targets<=30)).any() else None}


class ExperimentPredictor:
    """Explicit offline loader. Production Predictor cannot load experiment manifests."""
    def __init__(self, directory, trusted_manifest_sha256):
        root = Path(directory)
        if sha256(root/'experiment.json') != trusted_manifest_sha256:
            raise ValueError('Experiment manifest checksum mismatch')
        meta = json.loads((root/'experiment.json').read_text())
        if meta['schema'] != SCHEMA or meta['features'] != feature_names():
            raise ValueError('Incompatible experiment schema')
        for filename in ('model.json', 'transform.json', 'interval.json'):
            if sha256(root/filename) != meta['sha256'][filename]:
                raise ValueError('Experiment artifact checksum mismatch')
        self.meta = meta
        self.model = PointModel.load(root/'model.json', meta['family'])
        self.transform = json.loads((root/'transform.json').read_text())
        self.calibration = json.loads((root/'interval.json').read_text())

    def predict(self, subset, records):
        if subset != self.meta['subset']:
            return {'status': 'unavailable', 'reason': 'incompatible_subset'}
        frame = validate_frame(pd.DataFrame(records, columns=COLUMNS))
        if frame.engine_id.nunique() != 1:
            raise ValueError('One engine required')
        window = self.meta['window']
        if len(frame) < window:
            return {'status': 'unavailable', 'reason': 'insufficient_history'}
        transformed = transform_frame(frame.tail(window), self.transform)
        prediction = float(self.model.predict(window_features(transformed[VALUES].to_numpy())[None, :])[0])
        radius = self.calibration['radius_cycles']
        interval = None
        reason = 'insufficient_interval_history'
        if frame.cycle.iloc[-1] >= MIN_CUTOFF and radius is not None:
            interval = {'lower_cycles': max(0, prediction-radius), 'upper_cycles': prediction+radius,
                'nominal_coverage': self.calibration['nominal_coverage'], 'empirical_validation_required': True}
            reason = None
        elif radius is None:
            reason = 'insufficient_calibration_engines'
        return {'status': 'available', 'rul_cycles': prediction, 'interval': interval,
                'interval_unavailable_reason': reason, 'release_status': 'offline_experiment_only',
                'failure_probability': None}
