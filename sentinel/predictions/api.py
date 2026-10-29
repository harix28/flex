"""Session-authenticated persistent prediction and maintenance priority API routes."""
from contextlib import contextmanager
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import text
from sentinel.auth.context import AuthContext
from sentinel.auth.service import lock_tenant
from .schemas import PredictionCreate, MAX_CYCLE
from .policy import DEFAULT_POLICY, PriorityBand
from . import service


def predictions_router(database, settings, predictor):
    router = APIRouter(tags=['Persistent RUL predictions and maintenance priority'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request, tenant: UUID, permission: str, write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant)
                actor = auth.principal(s, request)
            auth.membership(s, actor, tenant, permission)
            yield s, actor

    @contextmanager
    def resolve_machine_tenant(request, machine_id: UUID, permission: str, write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            row = s.execute(text('SELECT tenant_id FROM machines WHERE id=:m'), dict(m=machine_id)).mappings().one_or_none()
            if row is None:
                raise HTTPException(404, 'not_found')
            tenant_id = row['tenant_id']
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant_id)
                actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor, tenant_id

    @contextmanager
    def resolve_prediction_tenant(request, prediction_id: UUID, permission: str):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            row = s.execute(text('SELECT tenant_id FROM predictions WHERE id=:id'), dict(id=prediction_id)).mappings().one_or_none()
            if row is None:
                raise HTTPException(404, 'not_found')
            tenant_id = row['tenant_id']
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor, tenant_id

    # 1. POST /api/v1/machines/{machine_id}/predictions & /api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions
    @router.post('/api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions')
    def create_prediction_org(tenant_id: UUID, machine_id: UUID, request: Request, payload: PredictionCreate | None = None):
        cutoff = payload.cutoff_cycle if payload else None
        with scoped_tenant(request, tenant_id, 'predictions.create', write=True) as (s, actor):
            result = service.compute_and_persist(
                s, tenant_id, machine_id, actor['user_id'], request.state.request_id,
                predictor, cutoff_cycle=cutoff, policy=DEFAULT_POLICY
            )
            return {'prediction': result, 'request_id': request.state.request_id}

    @router.post('/api/v1/machines/{machine_id}/predictions')
    def create_prediction(machine_id: UUID, request: Request, payload: PredictionCreate | None = None):
        cutoff = payload.cutoff_cycle if payload else None
        with resolve_machine_tenant(request, machine_id, 'predictions.create', write=True) as (s, actor, tenant_id):
            result = service.compute_and_persist(
                s, tenant_id, machine_id, actor['user_id'], request.state.request_id,
                predictor, cutoff_cycle=cutoff, policy=DEFAULT_POLICY
            )
            return {'prediction': result, 'request_id': request.state.request_id}

    # 2. GET /api/v1/machines/{machine_id}/predictions & /api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions
    @router.get('/api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions')
    def list_predictions_org(
        tenant_id: UUID, machine_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        status: Literal['available', 'unavailable'] | None = None,
    ):
        with scoped_tenant(request, tenant_id, 'predictions.read') as (s, _):
            res = service.list_machine_predictions(s, tenant_id, machine_id, limit, offset, status)
            return dict(res, request_id=request.state.request_id)

    @router.get('/api/v1/machines/{machine_id}/predictions')
    def list_predictions(
        machine_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        status: Literal['available', 'unavailable'] | None = None,
    ):
        with resolve_machine_tenant(request, machine_id, 'predictions.read') as (s, _, tenant_id):
            res = service.list_machine_predictions(s, tenant_id, machine_id, limit, offset, status)
            return dict(res, request_id=request.state.request_id)

    # 3. GET /api/v1/machines/{machine_id}/predictions/latest & /api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions/latest
    @router.get('/api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions/latest')
    def get_latest_prediction_org(tenant_id: UUID, machine_id: UUID, request: Request):
        with scoped_tenant(request, tenant_id, 'predictions.read') as (s, _):
            pred = service.get_latest_prediction(s, tenant_id, machine_id)
            return {'prediction': pred, 'request_id': request.state.request_id}

    @router.get('/api/v1/machines/{machine_id}/predictions/latest')
    def get_latest_prediction(machine_id: UUID, request: Request):
        with resolve_machine_tenant(request, machine_id, 'predictions.read') as (s, _, tenant_id):
            pred = service.get_latest_prediction(s, tenant_id, machine_id)
            return {'prediction': pred, 'request_id': request.state.request_id}

    # 4. GET /api/v1/predictions/{prediction_id} & /api/v1/organizations/{tenant_id}/predictions/{prediction_id}
    @router.get('/api/v1/organizations/{tenant_id}/predictions/{prediction_id}')
    def get_prediction_detail_org(tenant_id: UUID, prediction_id: UUID, request: Request):
        with scoped_tenant(request, tenant_id, 'predictions.read') as (s, _):
            pred = service.get_prediction_by_id(s, tenant_id, prediction_id)
            return {'prediction': pred, 'request_id': request.state.request_id}

    @router.get('/api/v1/predictions/{prediction_id}')
    def get_prediction_detail(prediction_id: UUID, request: Request):
        with resolve_prediction_tenant(request, prediction_id, 'predictions.read') as (s, _, tenant_id):
            pred = service.get_prediction_by_id(s, tenant_id, prediction_id)
            return {'prediction': pred, 'request_id': request.state.request_id}

    # 5. GET /api/v1/maintenance-priorities & /api/v1/organizations/{tenant_id}/maintenance-priorities
    @router.get('/api/v1/organizations/{tenant_id}/maintenance-priorities')
    def get_maintenance_priorities_org(
        tenant_id: UUID, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        priority_band: PriorityBand | None = None,
    ):
        with scoped_tenant(request, tenant_id, 'predictions.read') as (s, _):
            res = service.get_maintenance_priorities(s, tenant_id, limit, offset, priority_band, DEFAULT_POLICY)
            return dict(res, request_id=request.state.request_id)

    @router.get('/api/v1/maintenance-priorities')
    def get_maintenance_priorities(
        request: Request,
        tenant_id: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        priority_band: PriorityBand | None = None,
    ):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if tenant_id is not None:
                tid = tenant_id
            else:
                memberships = s.execute(
                    text('SELECT tenant_id FROM memberships WHERE user_id=:u AND active'),
                    dict(u=actor['user_id'])
                ).scalars().all()
                if not memberships:
                    raise HTTPException(404, 'no_tenant_membership')
                tid = memberships[0]
            auth.membership(s, actor, tid, 'predictions.read')
            res = service.get_maintenance_priorities(s, tid, limit, offset, priority_band, DEFAULT_POLICY)
            return dict(res, request_id=request.state.request_id)

    return router
