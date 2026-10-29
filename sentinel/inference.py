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
