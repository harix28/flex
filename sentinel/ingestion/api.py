"""Session-authenticated bounded replay ingestion/history; never physical ingestion."""
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Request,Query,Header
from sentinel.auth.context import AuthContext
from sentinel.auth.service import lock_tenant
from .schemas import Batch,MAX_CYCLE
from . import service


def ingestion_router(database,settings):
    router=APIRouter(prefix='/api/v1/organizations/{tenant_id}',tags=['Persistent NASA replay'])
    auth=AuthContext(database,settings)

    @contextmanager
    def scope(request,tenant,write=False):
        with auth.transaction(request) as s:
            actor=auth.principal(s,request)
            if write:
                auth.csrf(request,actor)
                lock_tenant(s,tenant)
                actor=auth.principal(s,request)
            auth.membership(s,actor,tenant,'replay.ingest' if write else 'replay.read')
            yield s,actor

    @router.post('/machines/{machine_id}/replay-batches')
    def ingest(tenant_id:UUID,machine_id:UUID,payload:Batch,request:Request,
               idempotency_key:Annotated[str,Header(pattern=r'^[A-Za-z0-9._:-]{1,128}$')]):
        with scope(request,tenant_id,True) as (s,actor):
            outcome=service.ingest(s,tenant_id,machine_id,actor['user_id'],request.state.request_id,payload,idempotency_key)
        return dict(outcome,request_id=request.state.request_id)

    @router.get('/machines/{machine_id}/observations')
    def history(tenant_id:UUID,machine_id:UUID,request:Request,
                start_cycle:Annotated[int,Query(ge=1,le=MAX_CYCLE)]=1,
                end_cycle:Annotated[int,Query(ge=1,le=MAX_CYCLE)]=MAX_CYCLE,
                after_cycle:Annotated[int,Query(ge=0,le=MAX_CYCLE)]=0,
                limit:Annotated[int,Query(ge=1,le=500)]=100):
        with scope(request,tenant_id) as (s,actor):
            return dict(service.history(s,tenant_id,machine_id,start_cycle,end_cycle,after_cycle,limit),request_id=request.state.request_id)

    @router.get('/machines/{machine_id}/data-quality')
    def quality(tenant_id:UUID,machine_id:UUID,request:Request,
                start_cycle:Annotated[int,Query(ge=1,le=MAX_CYCLE)]=1,
                end_cycle:Annotated[int|None,Query(ge=1,le=MAX_CYCLE)]=None):
        with scope(request,tenant_id) as (s,actor):
            return dict(service.quality(s,tenant_id,machine_id,start_cycle,end_cycle),request_id=request.state.request_id)

    @router.get('/ingestion-batches/{batch_id}')
    def batch(tenant_id:UUID,batch_id:UUID,request:Request):
        with scope(request,tenant_id) as (s,actor):
            return dict(service.read_batch(s,tenant_id,batch_id),request_id=request.state.request_id)
    return router
