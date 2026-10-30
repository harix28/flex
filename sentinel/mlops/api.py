"""REST API endpoints for tenant-scoped MLOps model information, observability, and monitoring."""
from contextlib import contextmanager
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sentinel.config import ROOT
from sentinel.auth.context import AuthContext
from sentinel.auth.service import lock_tenant
from sentinel.mlops.observability import get_tenant_observability
from sentinel.mlops.registry import get_model
from sentinel.mlops.deployment import get_deployment_status
from sentinel.mlops.drift import evaluate_input_drift
from sentinel.mlops.evaluation import evaluate_predictions_performance


def mlops_router(database, settings, predictor=None) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}/ml', tags=['mlops'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'predictions.read', write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant_id)
                actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.get('/model-info')
    def get_model_info(
        organization_id: UUID,
        request: Request
    ):
        """Returns safe metadata for the active serving model and its frozen benchmark metrics."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            running_version = predictor.meta.get('version') if predictor else None
            if not running_version:
                return {
                    'status': 'unavailable',
                    'active_model': None,
                    'message': 'No predictive model currently active in backend process'
                }

            model_record = get_model(s, running_version)
            dep_status = get_deployment_status(s, predictor)

            if model_record is None:
                meta = predictor.meta
                return {
                    'status': 'active_unregistered',
                    'model_version': meta.get('version'),
                    'model_family': meta.get('model_type'),
                    'bundle_digest': predictor.bundle_sha256,
                    'feature_schema': meta.get('feature_schema'),
                    'feature_count': len(meta['feature_names']),
                    'target_machine_type': 'cmapss_engine',
                    'target_data_source': 'nasa_replay',
                    'release_status': 'experiment_only',
                    'deployment_state': dep_status['state'],
                    'window_size': meta.get('window'),
                    'target_subset': meta.get('subset'),
                    'review_status': 'experiment_only',
                    'benchmark_metrics': predictor.report.get('official_test', {}),
                    'benchmark_protocol': predictor.report.get('test_protocol', 'One final trailing window per test engine'),
                    'disclaimer': 'Simulated turbofan demonstration — not certified for aircraft systems.'
                }

            if (model_record['bundle_digest'] != predictor.bundle_sha256
                    or model_record['model_digest'] != predictor.meta.get('model_sha256')):
                return {'status': 'incompatible_registry', 'deployment_state': 'active_untracked',
                        'message': 'Running artifact does not match the registered identity'}
            eval_metrics = model_record['evaluation_metrics']
            supported_models = {}
            if predictor and hasattr(predictor, 'predictors'):
                for sub, p in predictor.predictors.items():
                    supported_models[sub] = {
                        'version': p.meta.get('version'),
                        'model_type': p.meta.get('model_type'),
                        'window': p.meta.get('window'),
                        'subset': sub,
                        'metrics': p.report.get('official_test', {}),
                    }

            return {
                'status': 'active',
                'supported_models': supported_models,
                'model_version': model_record['model_version'],
                'model_family': model_record['model_family'],
                'bundle_digest': model_record['bundle_digest'],
                'feature_schema': model_record['feature_schema'],
                'feature_count': model_record['feature_count'],
                'window_size': model_record['window_size'],
                'target_subset': model_record['target_subset'],
                'target_machine_type': model_record['target_machine_type'],
                'target_data_source': model_record['target_data_source'],
                'review_status': model_record['review_status'],
                'release_status': 'experiment_only',
                'deployment_state': dep_status['state'],
                'benchmark_metrics': eval_metrics.get('official_test', {}),
                'benchmark_protocol': model_record['training_provenance'].get('validation_protocol'),
                'disclaimer': 'Simulated turbofan demonstration — experimental model only.'
            }

    @router.get('/observability')
    def get_observability(
        organization_id: UUID,
        request: Request
    ):
        """Returns aggregated operational telemetry and inference latencies strictly for this tenant."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            obs = get_tenant_observability(s, organization_id)
            return obs

    @router.get('/monitoring')
    def list_monitoring_runs(
        organization_id: UUID,
        request: Request,
        run_type: str | None = Query(None, pattern='^(drift|evaluation)$'),
        limit: int = Query(20, ge=1, le=50),
        offset: int = Query(0, ge=0)
    ):
        """Lists input drift and evaluation monitoring runs executed for this tenant."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            query = """SELECT id, model_version, run_type, status, sample_count, engine_count, actor, created_at,
                              metrics->>'drift_detected' as drift_detected,
                              metrics->>'mae_cycles' as mae_cycles,
                              metrics->>'rmse_cycles' as rmse_cycles,
                              metrics->>'message' as message
                       FROM ml_monitoring_runs
                       WHERE tenant_id = :t"""
            params = {'t': organization_id, 'lim': limit, 'off': offset}
            if run_type:
                query += " AND run_type = :rt"
                params['rt'] = run_type
            query += " ORDER BY created_at DESC LIMIT :lim OFFSET :off"

            rows = s.execute(text(query), params).mappings().all()

            runs = []
            for r in rows:
                runs.append({
                    'id': str(r['id']),
                    'model_version': r['model_version'],
                    'run_type': r['run_type'],
                    'status': r['status'],
                    'sample_count': r['sample_count'],
                    'engine_count': r['engine_count'],
                    'actor': r['actor'],
                    'created_at': r['created_at'].isoformat(),
                    'summary': {
                        'drift_detected': r['drift_detected'] == 'true' if r['drift_detected'] is not None else None,
                        'mae_cycles': float(r['mae_cycles']) if r['mae_cycles'] is not None else None,
                        'rmse_cycles': float(r['rmse_cycles']) if r['rmse_cycles'] is not None else None,
                        'message': r['message']
                    }
                })
            return {'runs': runs, 'limit': limit, 'offset': offset}

    @router.get('/monitoring/{run_id}')
    def get_monitoring_run_detail(
        organization_id: UUID,
        run_id: UUID,
        request: Request
    ):
        """Retrieves detailed metrics and feature breakdowns for a specific monitoring run."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            row = s.execute(
                text("SELECT * FROM ml_monitoring_runs WHERE id = :id AND tenant_id = :t"),
                {'id': run_id, 't': organization_id}
            ).mappings().one_or_none()

            if row is None:
                raise HTTPException(404, 'monitoring_run_not_found')

            return {
                'id': str(row['id']),
                'tenant_id': str(row['tenant_id']),
                'model_version': row['model_version'],
                'run_type': row['run_type'],
                'status': row['status'],
                'sample_count': row['sample_count'],
                'engine_count': row['engine_count'],
                'actor': row['actor'],
                'created_at': row['created_at'].isoformat(),
                'metrics': row['metrics']
            }

    @router.post('/monitoring/drift')
    def trigger_drift_run(
        organization_id: UUID,
        request: Request,
        min_samples: int = Query(5, ge=1, le=1000)
    ):
        """Triggers an input feature drift monitoring run for this tenant."""
        with scoped_tenant(request, organization_id, 'predictions.create', write=True) as (s, actor):
            actor_name = f"user:{actor.get('email', actor.get('id', 'admin'))}"
            running_version = predictor.meta.get('version', 'fd001-v1') if predictor else 'fd001-v1'
            result = evaluate_input_drift(s, organization_id, model_version=running_version, actor=actor_name, min_samples=min_samples)
            return result

    @router.post('/monitoring/evaluation')
    def trigger_evaluation_run(
        organization_id: UUID,
        request: Request,
        subset: str = Query('FD001', pattern='^(FD001|FD002|FD003|FD004)$')
    ):
        """Triggers an offline ground-truth performance evaluation run against reference labels."""
        with scoped_tenant(request, organization_id, 'predictions.create', write=True) as (s, actor):
            actor_name = f"user:{actor.get('email', actor.get('id', 'admin'))}"
            labels_path = ROOT / 'data' / 'raw' / f'RUL_{subset}.txt'
            if not labels_path.exists():
                raise HTTPException(404, 'labels_file_not_found')
            running_version = predictor.meta.get('version', 'fd001-v1') if predictor else 'fd001-v1'
            result = evaluate_predictions_performance(
                s, organization_id, labels_path=labels_path, subset=subset, model_version=running_version, actor=actor_name
            )
            return result

    @router.post('/pipeline/evaluate-candidate')
    def evaluate_candidate(
        organization_id: UUID,
        request: Request,
        candidate_version: str = Query('fd001-v2-candidate'),
        candidate_test_mae: float = Query(15.80),
        near_failure_candidate: float = Query(4.20),
        candidate_hash: str = Query('a' * 64)
    ):
        """Runs the automated candidate evaluation pipeline and checks promotion gates."""
        with scoped_tenant(request, organization_id, 'predictions.create') as (s, actor):
            from sentinel.mlops.pipeline import evaluate_candidate_gate
            active_version = predictor.meta.get('version', 'fd001-v1') if predictor else 'fd001-v1'
            active_hash = predictor.bundle_sha256 if predictor else '0' * 64
            active_test_mae = 16.14
            near_failure_active = 4.00

            res = evaluate_candidate_gate(
                candidate_version=candidate_version,
                active_version=active_version,
                active_test_mae=active_test_mae,
                candidate_test_mae=candidate_test_mae,
                near_failure_active=near_failure_active,
                near_failure_candidate=near_failure_candidate,
                candidate_hash=candidate_hash,
                active_hash=active_hash
            )
            return res

    @router.get('/pipeline/candidates')
    def get_candidate_evaluations(organization_id: UUID, request: Request):
        """Lists candidate model runs and evaluation gate outcomes."""
        with scoped_tenant(request, organization_id, 'predictions.read'):
            from sentinel.mlops.pipeline import list_candidate_evaluations
            return {'items': list_candidate_evaluations()}

    @router.post('/shadow/configure')
    def configure_shadow_serving(
        organization_id: UUID,
        request: Request,
        enabled: bool = Query(...),
        version: str | None = Query(None)
    ):
        """Configures shadow model scoring alongside production inference."""
        with scoped_tenant(request, organization_id, 'predictions.create'):
            from sentinel.mlops.shadow import shadow_manager
            shadow_manager.configure(enabled, version)
            return {'shadow_enabled': enabled, 'shadow_version': version}

    @router.get('/shadow/metrics')
    def get_shadow_metrics(organization_id: UUID, request: Request):
        """Reports real-time prediction divergence metrics between active and shadow models."""
        with scoped_tenant(request, organization_id, 'predictions.read'):
            from sentinel.mlops.shadow import shadow_manager
            return {'metrics': shadow_manager.get_metrics()}

    return router
