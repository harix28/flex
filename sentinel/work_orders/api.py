"""Session-authenticated maintenance work orders, approval workflow, and notes API routes."""
from contextlib import contextmanager
from datetime import date
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Request, Query, HTTPException, Header
from sqlalchemy import text
from pydantic import AwareDatetime
from sentinel.auth.context import AuthContext
from sentinel.auth.service import lock_tenant
from .schemas import (
    WorkOrderCreateManual,
    WorkOrderCreateFromPrediction,
    WorkOrderUpdate,
    WorkOrderAssign,
    WorkOrderTransition,
    WorkOrderNoteCreate,
    WorkOrderStatus,
    WorkOrderPriority,
)
from . import service


def work_orders_router(database, settings):
    router = APIRouter(tags=['Maintenance work orders and approval workflow'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request, tenant: UUID, permission: str, write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant)
                actor = auth.principal(s, request)
            member = auth.membership(s, actor, tenant, permission)
            yield s, actor, member

    @contextmanager
    def resolve_work_order_tenant(request, work_order_id: UUID, permission: str, write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            row = s.execute(
                text('SELECT tenant_id FROM work_orders WHERE id=:id'),
                dict(id=work_order_id)
            ).mappings().one_or_none()
            if row is None:
                raise HTTPException(404, 'not_found')
            tenant_id = row['tenant_id']
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant_id)
                actor = auth.principal(s, request)
            member = auth.membership(s, actor, tenant_id, permission)
            yield s, actor, tenant_id, member

    @contextmanager
    def resolve_prediction_tenant(request, prediction_id: UUID, permission: str, write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            row = s.execute(
                text('SELECT tenant_id FROM predictions WHERE id=:id'),
                dict(id=prediction_id)
            ).mappings().one_or_none()
            if row is None:
                raise HTTPException(404, 'not_found')
            tenant_id = row['tenant_id']
            if write:
                auth.csrf(request, actor)
                lock_tenant(s, tenant_id)
                actor = auth.principal(s, request)
            member = auth.membership(s, actor, tenant_id, permission)
            yield s, actor, tenant_id, member

    def get_idempotency_key(request: Request, payload_key: str | None = None) -> str | None:
        header_key = request.headers.get('idempotency-key')
        return (header_key.strip() if header_key and header_key.strip() else None) or payload_key

    # 1. POST /api/v1/predictions/{prediction_id}/work-order-draft
    @router.post('/api/v1/organizations/{tenant_id}/predictions/{prediction_id}/work-order-draft')
    def create_draft_from_prediction_org(
        tenant_id: UUID,
        prediction_id: UUID,
        request: Request,
        payload: WorkOrderCreateFromPrediction | None = None,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.create', write=True) as (s, actor, _):
            key = get_idempotency_key(request, payload.idempotency_key if payload else None)
            res = service.create_draft_from_prediction(
                s,
                tenant=tenant_id,
                prediction_id=prediction_id,
                actor_id=actor['user_id'],
                title=payload.title if payload else None,
                description=payload.description if payload else None,
                priority=payload.priority if payload else None,
                due_date=payload.due_date if payload else None,
                planned_date=payload.planned_date if payload else None,
                idempotency_key=key,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    @router.post('/api/v1/predictions/{prediction_id}/work-order-draft')
    def create_draft_from_prediction(
        prediction_id: UUID,
        request: Request,
        payload: WorkOrderCreateFromPrediction | None = None,
    ):
        with resolve_prediction_tenant(request, prediction_id, 'work_orders.create', write=True) as (s, actor, tenant_id, _):
            key = get_idempotency_key(request, payload.idempotency_key if payload else None)
            res = service.create_draft_from_prediction(
                s,
                tenant=tenant_id,
                prediction_id=prediction_id,
                actor_id=actor['user_id'],
                title=payload.title if payload else None,
                description=payload.description if payload else None,
                priority=payload.priority if payload else None,
                due_date=payload.due_date if payload else None,
                planned_date=payload.planned_date if payload else None,
                idempotency_key=key,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    # 2. POST /api/v1/work-orders (Manual draft)
    @router.post('/api/v1/organizations/{tenant_id}/work-orders')
    def create_manual_work_order_org(
        tenant_id: UUID,
        payload: WorkOrderCreateManual,
        request: Request,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.create', write=True) as (s, actor, _):
            key = get_idempotency_key(request, payload.idempotency_key)
            res = service.create_manual_draft(
                s,
                tenant=tenant_id,
                machine_id=payload.machine_id,
                actor_id=actor['user_id'],
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                due_date=payload.due_date,
                planned_date=payload.planned_date,
                idempotency_key=key,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    @router.post('/api/v1/work-orders')
    def create_manual_work_order(
        payload: WorkOrderCreateManual,
        request: Request,
        tenant_id: UUID | None = None,
    ):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if tenant_id is not None:
                tid = tenant_id
            else:
                mach = s.execute(
                    text('SELECT tenant_id FROM machines WHERE id=:m'),
                    dict(m=payload.machine_id)
                ).mappings().one_or_none()
                if mach is None:
                    raise HTTPException(404, 'machine_not_found')
                tid = mach['tenant_id']
            auth.csrf(request, actor)
            lock_tenant(s, tid)
            actor = auth.principal(s, request)
            auth.membership(s, actor, tid, 'work_orders.create')
            key = get_idempotency_key(request, payload.idempotency_key)
            res = service.create_manual_draft(
                s,
                tenant=tid,
                machine_id=payload.machine_id,
                actor_id=actor['user_id'],
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                due_date=payload.due_date,
                planned_date=payload.planned_date,
                idempotency_key=key,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    # 3. GET /api/v1/work-orders (List)
    @router.get('/api/v1/organizations/{tenant_id}/work-orders')
    def list_work_orders_org(
        tenant_id: UUID,
        request: Request,
        machine_id: UUID | None = None,
        status: WorkOrderStatus | None = None,
        priority: WorkOrderPriority | None = None,
        technician_id: UUID | None = None,
        created_from: AwareDatetime | None = None,
        created_to: AwareDatetime | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.read') as (s, _, _):
            items, total = service.list_work_orders(
                s, tenant_id, machine_id=machine_id, status=status,
                priority=priority, technician_id=technician_id, limit=limit, offset=offset,
                created_from=created_from, created_to=created_to, due_from=due_from, due_to=due_to
            )
            return {
                'items': items,
                'total': total,
                'limit': limit,
                'offset': offset,
                'request_id': request.state.request_id,
            }

    @router.get('/api/v1/work-orders')
    def list_work_orders(
        request: Request,
        tenant_id: UUID | None = None,
        machine_id: UUID | None = None,
        status: WorkOrderStatus | None = None,
        priority: WorkOrderPriority | None = None,
        technician_id: UUID | None = None,
        created_from: AwareDatetime | None = None,
        created_to: AwareDatetime | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
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
            auth.membership(s, actor, tid, 'work_orders.read')
            items, total = service.list_work_orders(
                s, tid, machine_id=machine_id, status=status,
                priority=priority, technician_id=technician_id, limit=limit, offset=offset,
                created_from=created_from, created_to=created_to, due_from=due_from, due_to=due_to
            )
            return {
                'items': items,
                'total': total,
                'limit': limit,
                'offset': offset,
                'request_id': request.state.request_id,
            }

    # 4. GET /api/v1/work-orders/{work_order_id}
    @router.get('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}')
    def get_work_order_org(tenant_id: UUID, work_order_id: UUID, request: Request):
        with scoped_tenant(request, tenant_id, 'work_orders.read') as (s, _, _):
            wo = service.get_work_order_raw(s, tenant_id, work_order_id)
            view = service.build_work_order_view(s, wo)
            return {'work_order': view, 'request_id': request.state.request_id}

    @router.get('/api/v1/work-orders/{work_order_id}')
    def get_work_order(work_order_id: UUID, request: Request):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.read') as (s, _, tenant_id, _):
            wo = service.get_work_order_raw(s, tenant_id, work_order_id)
            view = service.build_work_order_view(s, wo)
            return {'work_order': view, 'request_id': request.state.request_id}

    # 5. PATCH /api/v1/work-orders/{work_order_id} (Update allowed fields)
    @router.patch('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}')
    def update_work_order_org(
        tenant_id: UUID,
        work_order_id: UUID,
        payload: WorkOrderUpdate,
        request: Request,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.update', write=True) as (s, actor, _):
            res = service.update_work_order(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                expected_version=payload.version,
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                due_date=payload.due_date,
                planned_date=payload.planned_date,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    @router.patch('/api/v1/work-orders/{work_order_id}')
    def update_work_order(
        work_order_id: UUID,
        payload: WorkOrderUpdate,
        request: Request,
    ):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.update', write=True) as (s, actor, tenant_id, _):
            res = service.update_work_order(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                expected_version=payload.version,
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                due_date=payload.due_date,
                planned_date=payload.planned_date,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    # 6. POST /api/v1/work-orders/{work_order_id}/assignment
    @router.post('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}/assignment')
    def assign_technician_org(
        tenant_id: UUID,
        work_order_id: UUID,
        payload: WorkOrderAssign,
        request: Request,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.assign', write=True) as (s, actor, _):
            res = service.assign_technician(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                technician_id=payload.technician_id,
                expected_version=payload.version,
                reason=payload.reason,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    @router.post('/api/v1/work-orders/{work_order_id}/assignment')
    def assign_technician(
        work_order_id: UUID,
        payload: WorkOrderAssign,
        request: Request,
    ):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.assign', write=True) as (s, actor, tenant_id, _):
            res = service.assign_technician(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                technician_id=payload.technician_id,
                expected_version=payload.version,
                reason=payload.reason,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    # 7. POST /api/v1/work-orders/{work_order_id}/transitions
    @router.post('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}/transitions')
    def transition_work_order_org(
        tenant_id: UUID,
        work_order_id: UUID,
        payload: WorkOrderTransition,
        request: Request,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.read', write=True) as (s, actor, member):
            res = service.transition_work_order(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                actor_roles=member['roles'],
                action=payload.action,
                expected_version=payload.version,
                reason=payload.reason,
                completion_summary=payload.completion_summary,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    @router.post('/api/v1/work-orders/{work_order_id}/transitions')
    def transition_work_order(
        work_order_id: UUID,
        payload: WorkOrderTransition,
        request: Request,
    ):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.read', write=True) as (s, actor, tenant_id, member):
            res = service.transition_work_order(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                actor_id=actor['user_id'],
                actor_roles=member['roles'],
                action=payload.action,
                expected_version=payload.version,
                reason=payload.reason,
                completion_summary=payload.completion_summary,
                request_id=request.state.request_id,
            )
            return {'work_order': res, 'request_id': request.state.request_id}

    # 8. POST /api/v1/work-orders/{work_order_id}/notes
    @router.post('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}/notes')
    def add_note_org(
        tenant_id: UUID,
        work_order_id: UUID,
        payload: WorkOrderNoteCreate,
        request: Request,
    ):
        with scoped_tenant(request, tenant_id, 'work_orders.notes', write=True) as (s, actor, member):
            note, work_order_version = service.add_note(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                author_id=actor['user_id'],
                actor_roles=member['roles'],
                note_text=payload.note_text,
                expected_version=payload.version,
                request_id=request.state.request_id,
            )
            return {'note': note, 'work_order_version': work_order_version, 'request_id': request.state.request_id}

    @router.post('/api/v1/work-orders/{work_order_id}/notes')
    def add_note(
        work_order_id: UUID,
        payload: WorkOrderNoteCreate,
        request: Request,
    ):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.notes', write=True) as (s, actor, tenant_id, member):
            note, work_order_version = service.add_note(
                s,
                tenant=tenant_id,
                work_order_id=work_order_id,
                author_id=actor['user_id'],
                actor_roles=member['roles'],
                note_text=payload.note_text,
                expected_version=payload.version,
                request_id=request.state.request_id,
            )
            return {'note': note, 'work_order_version': work_order_version, 'request_id': request.state.request_id}

    # 9. GET /api/v1/work-orders/{work_order_id}/history
    @router.get('/api/v1/organizations/{tenant_id}/work-orders/{work_order_id}/history')
    def get_work_order_history_org(tenant_id: UUID, work_order_id: UUID, request: Request):
        with scoped_tenant(request, tenant_id, 'work_orders.read') as (s, _, _):
            hist = service.get_work_order_history(s, tenant_id, work_order_id)
            return dict(hist, request_id=request.state.request_id)

    @router.get('/api/v1/work-orders/{work_order_id}/history')
    def get_work_order_history(work_order_id: UUID, request: Request):
        with resolve_work_order_tenant(request, work_order_id, 'work_orders.read') as (s, _, tenant_id, _):
            hist = service.get_work_order_history(s, tenant_id, work_order_id)
            return dict(hist, request_id=request.state.request_id)

    return router
