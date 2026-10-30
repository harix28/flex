import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from .data import COLUMNS, VALUES, SUBSETS, validate_frame, sha256
from .features import SCHEMA, feature_names, window_features


class Predictor:
    def __init__(self, directory, expected_manifest_sha256):
        root = Path(directory)
        if sha256(root/'bundle.json') != expected_manifest_sha256:
            raise ValueError('Bundle manifest hash mismatch')
        self.bundle_sha256 = expected_manifest_sha256
        self.meta = json.loads((root/'bundle.json').read_text())
        m = self.meta
        if m['feature_schema'] != SCHEMA or m['feature_names'] != feature_names():
            raise ValueError('Incompatible feature schema')
        if m['subset'] not in SUBSETS or not 2 <= m['window'] <= 1000:
            raise ValueError('Invalid bundle configuration')
        if sha256(root/'model.json') != m['model_sha256'] or sha256(root/'report.json') != m['report_sha256']:
            raise ValueError('Artifact hash mismatch')
        self.report = json.loads((root/'report.json').read_text())
        if m['model_type'] == 'xgboost':
            self.model = XGBRegressor()
            self.model.load_model(root/'model.json')
        elif m['model_type'] in ('ridge','constant'):
            self.model = json.loads((root/'model.json').read_text())
        else:
            raise ValueError('Unsupported model type')

    def predict(self, subset, records):
        base = {'status':'unavailable','reason':None,'rul_cycles':None,
                'failure_probability':None,'interval':None,'diagnosis_basis':'unavailable',
                'model_version':self.meta['version'],'data_mode':'replay',
                'release_status':'experiment_only'}
        if subset != self.meta['subset']:
            return dict(base,reason='incompatible_subset')
        df = validate_frame(pd.DataFrame(records,columns=COLUMNS))
        if df.engine_id.nunique() != 1:
            raise ValueError('History must belong to one engine')
        window = self.meta['window']
        if len(df) < window:
            return dict(base,reason='insufficient_history')
        f = window_features(df[VALUES].tail(window).to_numpy())
        if self.meta['model_type'] == 'xgboost':
            result = self.model.predict(pd.DataFrame([f],columns=feature_names()))[0]
        elif self.meta['model_type'] == 'ridge':
            m = self.model
            result = ((f-np.asarray(m['mean']))/np.asarray(m['scale'])) @ np.asarray(m['coef'])+m['intercept']
        else:
            result = self.model['constant']
        if not np.isfinite(result):
            return dict(base,reason='nonfinite_model_output')
        return dict(base,status='available',rul_cycles=float(max(0,result)),
                    observed_cycle=int(df.cycle.iloc[-1]),input_window_cycles=window)


class MultiPredictor:
    def __init__(self, predictors: dict[str, Predictor]):
        if not predictors:
            raise ValueError('At least one Predictor is required')
        self.predictors = predictors
        default_pred = predictors.get('FD001') or next(iter(predictors.values()))
        self.meta = default_pred.meta
        self.bundle_sha256 = default_pred.bundle_sha256
        self.report = default_pred.report

    def supports_subset(self, subset: str) -> bool:
        return subset in self.predictors

    def get_meta(self, subset: str) -> dict:
        if subset in self.predictors:
            return self.predictors[subset].meta
        return self.meta

    def predict(self, subset: str, records: list):
        if subset not in self.predictors:
            return {
                'status': 'unavailable',
                'reason': 'incompatible_subset',
                'rul_cycles': None,
                'failure_probability': None,
                'interval': None,
                'diagnosis_basis': 'unavailable',
                'model_version': self.meta.get('version', 'unknown'),
                'data_mode': 'replay',
                'release_status': 'experiment_only',
            }
        return self.predictors[subset].predict(subset, records)


KNOWN_SUBSET_CANDIDATES = {
    'FD001': ('runs/fd001-20261027-candidate', '8c8369f735b5896756035325a4461b4a28a4b926f0c21cba7bddd2ef75dbef03'),
    'FD002': ('runs/fd002-20261027-candidate', 'a32dcc7cd7445f65366e6cb50eb41a262ef85278b09baa2fcc40108700529231'),
    'FD003': ('runs/fd003-20261027-candidate', 'bd258a5866a4eb110082b71072bd7cee66ee9d7e917aebd2c80b7a44ee30681e'),
    'FD004': ('runs/fd004-20261027-candidate', '19a1ca43a256942beeb09f76dc07e77565d9910f1d6b38ac58191255f2bd7b35'),
}


def load_multi_predictor(primary_dir=None, primary_hash=None, project_root=None) -> MultiPredictor:
    """Loads predictors for all available subsets (FD001..FD004)."""
    predictors = {}
    base_path = Path(project_root) if project_root else Path.cwd()

    # 1. Primary predictor
    if primary_dir and primary_hash:
        p_dir = Path(primary_dir)
        if not p_dir.is_absolute():
            p_dir = base_path / p_dir
        p = Predictor(p_dir, primary_hash)
        predictors[p.meta['subset']] = p

    # 2. Candidate predictors for remaining subsets
    for subset, (rel_dir, h) in KNOWN_SUBSET_CANDIDATES.items():
        if subset not in predictors:
            c_dir = base_path / rel_dir
            if c_dir.exists():
                try:
                    predictors[subset] = Predictor(c_dir, h)
                except Exception:
                    pass

    if not predictors and primary_dir and primary_hash:
        predictors['FD001'] = Predictor(primary_dir, primary_hash)

    return MultiPredictor(predictors)
