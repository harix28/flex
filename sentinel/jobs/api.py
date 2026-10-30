"""REST API endpoints for tenant-scoped asynchronous background jobs."""
from contextlib import contextmanager
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Request, Body
from sqlalchemy import text
from sentinel.auth.context import AuthContext
from sentinel.jobs.fleet import enqueue_fleet


def jobs_router(database, settings, predictor=None) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}/jobs', tags=['Background Jobs'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'predictions.read'):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.post('/fleet-score')
    def submit_fleet_scoring_job(organization_id: UUID, request: Request, payload: dict | None = Body(default=None)):
        """Submits an asynchronous fleet-wide scoring job to the PostgreSQL outbox queue."""
        if predictor is None:
            raise HTTPException(503, 'predictor_unavailable')

        source_event_id = f"fleet-score-{uuid4().hex[:12]}"
        machine_ids = None
        if payload and 'machine_ids' in payload:
            machine_ids = payload['machine_ids']

        with scoped_tenant(request, organization_id, 'predictions.create') as (s, actor):
            try:
                job_id = enqueue_fleet(s, organization_id, actor['user_id'], source_event_id, predictor, machine_ids=machine_ids)
                return {
                    'job_id': str(job_id),
                    'source_event_id': source_event_id,
                    'status': 'pending',
                    'event_type': 'fleet.score',
                    'notice': 'Fleet scoring job enqueued successfully. Background worker processes assets via PostgreSQL SKIP LOCKED leasing.'
                }
            except Exception as e:
                raise HTTPException(400, str(e))

    @router.get('')
    def list_jobs(organization_id: UUID, request: Request, limit: int = 50):
        """Lists background outbox jobs and their processing statuses for this tenant."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            rows = s.execute(text("""
                SELECT id, event_type, source_event_id, status, attempts, max_attempts,
                       error_code, created_at, completed_at, result
                FROM outbox_events
                WHERE tenant_id = :t
                ORDER BY created_at DESC
                LIMIT :limit
            """), {'t': organization_id, 'limit': min(limit, 100)}).mappings().all()

            items = []
            for r in rows:
                items.append({
                    'id': str(r['id']),
                    'event_type': r['event_type'],
                    'source_event_id': r['source_event_id'],
                    'status': r['status'],
                    'attempts': r['attempts'],
                    'max_attempts': r['max_attempts'],
                    'error_code': r['error_code'],
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                    'completed_at': r['completed_at'].isoformat() if r['completed_at'] else None,
                    'result': r['result']
                })
            return {'items': items, 'total': len(items)}

    @router.get('/{job_id}')
    def get_job_detail(organization_id: UUID, job_id: UUID, request: Request):
        """Retrieves details and execution results of a specific background job."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            row = s.execute(text("""
                SELECT id, event_type, source_event_id, status, attempts, max_attempts,
                       error_code, created_at, completed_at, result
                FROM outbox_events
                WHERE tenant_id = :t AND id = :id
            """), {'t': organization_id, 'id': job_id}).mappings().one_or_none()

            if not row:
                raise HTTPException(404, 'job_not_found')

            return {
                'id': str(row['id']),
                'event_type': row['event_type'],
                'source_event_id': row['source_event_id'],
                'status': row['status'],
                'attempts': row['attempts'],
                'max_attempts': row['max_attempts'],
                'error_code': row['error_code'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                'result': row['result']
            }

    return router

