"""Hash-pinned, read-only C-MAPSS lifetime-stage inference (not fault diagnosis)."""
import hashlib
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text

from .auth.context import AuthContext
from .data import VALUES, SUBSETS, sha256
from .ingestion import service
from .ingestion.schemas import MAX_CYCLE

VERSION = 'combined-rf-20261030-v1'
TRUSTED_MANIFEST = '3edb1bd6dc21d84f364d791ce2b5472486d01c9f6f28a4f3500d60af58b50bd9'
LABELS = ['early_lifetime', 'middle_lifetime', 'late_lifetime']


class LifetimeClassifier:
    def __init__(self, directory):
        directory = Path(directory)
        raw_json = (directory / 'forest.json').read_bytes()
        json_sha = hashlib.sha256(raw_json).hexdigest()
        crlf_sha = hashlib.sha256(raw_json.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest()
        if json_sha != TRUSTED_MANIFEST and crlf_sha != TRUSTED_MANIFEST:
            raise ValueError('Classifier manifest rejected')
        meta = json.loads(raw_json.decode('utf-8'))
        if (meta['features'] != ['cycle'] + VALUES or meta['classes'] != [0, 1, 2]
                or sha256(directory / 'forest.npz') != meta['forest_sha256']):
            raise ValueError('Classifier feature/artifact contract rejected')
        # Keep verified numeric arrays in memory. Never deserialize pickle.
        with np.load(directory / 'forest.npz', allow_pickle=False) as bundle:
            self.trees = [tuple(bundle[f'{i}_{n}'].copy() for n in
                               ('left', 'right', 'feature', 'threshold', 'value'))
                          for i in range(meta['trees'])]

    def predict(self, cycle, settings, sensors):
        if type(cycle) is not int or not 1 <= cycle <= MAX_CYCLE or len(settings) != 3 or len(sensors) != 21:
            raise ValueError('Invalid observation')
        row = np.asarray([cycle] + list(settings) + list(sensors), dtype=np.float64)
        if not np.isfinite(row).all() or np.abs(row).max() > np.finfo(np.float32).max:
            raise ValueError('Non-finite observation')
        row = row.astype(np.float32)
        votes = np.zeros(3)
        for left, right, feature, threshold, value in self.trees:
            node = 0
            while left[node] != -1:
                node = left[node] if row[feature[node]] <= threshold[node] else right[node]
            votes += value[node] / value[node].sum()
        return int(votes.argmax())


def classification_router(database, settings, classifier):
    router = APIRouter(prefix='/api/v1/organizations/{tenant_id}', tags=['Lifetime classification'])
    auth = AuthContext(database, settings)

    @router.get('/machines/{machine_id}/lifetime-classification')
    def classify(tenant_id: UUID, machine_id: UUID, request: Request,
                 cutoff_cycle: Annotated[int | None, Query(ge=1, le=MAX_CYCLE)] = None):
        # Read-only deterministic assessment. No maintenance mutations or API-key bypass.
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, 'replay.read')
            service.get_machine(s, tenant_id, machine_id)
            stream = service.get_stream(s, tenant_id, machine_id)
            if not stream:
                raise HTTPException(409, 'observations_unavailable')
            if stream['subset'] not in SUBSETS or stream['schema_version'] != 1:
                raise HTTPException(422, 'classifier_source_incompatible')
            row = s.execute(text('''SELECT cycle,settings,sensors FROM replay_observations
                WHERE tenant_id=:t AND machine_id=:m AND stream_id=:stream AND cycle<=:cutoff
                ORDER BY cycle DESC LIMIT 1'''),
                dict(t=tenant_id, m=machine_id, stream=stream['id'], cutoff=cutoff_cycle or MAX_CYCLE)).mappings().one_or_none()
            if row is None:
                raise HTTPException(409, 'observations_unavailable')
            if classifier is None:
                raise HTTPException(503, 'classifier_unavailable')
            try:
                label = classifier.predict(row['cycle'], row['settings'], row['sensors'])
            except ValueError:
                raise HTTPException(422, 'classifier_input_invalid') from None
            return dict(machine_id=machine_id, stream=dict(stream), source_cycle=row['cycle'],
                        requested_cutoff_cycle=cutoff_cycle, model_version=VERSION,
                        model_manifest_sha256=TRUSTED_MANIFEST, class_id=label, lifetime_stage=LABELS[label],
                        data_mode='replay', persisted=False,
                        interpretation='Estimated lifetime stage; not a physical health diagnosis or failure probability.',
                        label_policy='early <=60%, middle >60% to 80%, late >80% elapsed total lifetime',
                        request_id=request.state.request_id)
    return router
