"""Organization-scoped registry API; session authorization on every route."""
from contextlib import contextmanager
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Request, Query
from sqlalchemy import select
from sentinel.auth.context import AuthContext
from sentinel.auth.service import lock_tenant
from .schemas import MachineCreate,MachinePatch,SensorCreate,SensorPatch,InstallationCreate,InstallationRemove
from .service import Registry,machine_view,sensor_view,installation_view
from .channels import catalog


def registry_router(database,settings):
    router=APIRouter(prefix='/api/v1/organizations/{tenant_id}',tags=['Machine and sensor registry'])
    auth=AuthContext(database,settings)

    @contextmanager
    def scope(request,tenant,permission,write=False):
        with auth.transaction(request) as s:
            actor=auth.principal(s,request)
            if write:
                auth.csrf(request,actor)
                lock_tenant(s,tenant)
                actor=auth.principal(s,request)
            auth.membership(s,actor,tenant,permission)
            yield Registry(s,tenant,actor['user_id'],request.state.request_id)

    def result(request,**values): return dict(values,request_id=request.state.request_id)

    def page(r,table,limit,offset,conditions,view,order):
        t=r.repo._table(table)
        query=select(t).where(t.c.tenant_id==r.tenant)
        for name,value in conditions.items():
            if value is not None: query=query.where(t.c[name]==value)
        rows=r.s.execute(query.order_by(t.c[order],t.c.id).limit(limit+1).offset(offset)).mappings().all()
        return dict(items=[view(row) for row in rows[:limit]],next_offset=offset+limit if len(rows)>limit else None)

    @router.get('/registry/channels')
    def channels(tenant_id:UUID,request:Request):
        with scope(request,tenant_id,'registry.read'):
            return result(request,**catalog())

    @router.post('/machines',status_code=201)
    def create_machine(tenant_id:UUID,payload:MachineCreate,request:Request):
        with scope(request,tenant_id,'registry.manage',True) as r:
            return result(request,machine=r.create_machine(payload))

    @router.get('/machines')
    def machines(tenant_id:UUID,request:Request,limit:Annotated[int,Query(ge=1,le=100)]=25,
                 offset:Annotated[int,Query(ge=0,le=100000)]=0,
                 asset_code:Annotated[str|None,Query(max_length=64)]=None,
                 lifecycle_status:Literal['active','inactive','archived']|None=None,
                 data_source:Literal['nasa_replay','physical_device']|None=None,
                 machine_type:Annotated[str|None,Query(max_length=120)]=None,
                 site:Annotated[str|None,Query(max_length=120)]=None):
        with scope(request,tenant_id,'registry.read') as r:
            return result(request,**page(r,'machines',limit,offset,dict(asset_code=asset_code,lifecycle_status=lifecycle_status,
                          data_source=data_source,machine_type=machine_type,site=site),machine_view,'asset_code'))

    @router.get('/machines/{machine_id}')
    def machine(tenant_id:UUID,machine_id:UUID,request:Request):
        with scope(request,tenant_id,'registry.read') as r:
            return result(request,machine=machine_view(r.get('machines',machine_id)))

    @router.patch('/machines/{machine_id}')
    def update_machine(tenant_id:UUID,machine_id:UUID,payload:MachinePatch,request:Request):
        with scope(request,tenant_id,'registry.manage',True) as r:
            return result(request,machine=r.patch_machine(machine_id,payload))

    @router.post('/machines/{machine_id}/archive')
    def archive(tenant_id:UUID,machine_id:UUID,request:Request):
        with scope(request,tenant_id,'registry.manage',True) as r:
            return result(request,machine=r.archive(machine_id))

    @router.post('/sensors',status_code=201)
    def create_sensor(tenant_id:UUID,payload:SensorCreate,request:Request):
        with scope(request,tenant_id,'registry.manage',True) as r:
            return result(request,sensor=r.create_sensor(payload))

    @router.get('/sensors')
    def sensors(tenant_id:UUID,request:Request,limit:Annotated[int,Query(ge=1,le=100)]=25,
                offset:Annotated[int,Query(ge=0,le=100000)]=0,
                sensor_code:Annotated[str|None,Query(max_length=64)]=None,
                status:Literal['active','retired']|None=None,
                data_source:Literal['nasa_replay','physical_device']|None=None,
                kind:Annotated[str|None,Query(max_length=120)]=None,
                channel_id:Annotated[str|None,Query(max_length=32)]=None):
        with scope(request,tenant_id,'registry.read') as r:
            return result(request,**page(r,'sensors',limit,offset,dict(sensor_code=sensor_code,
                retired=None if status is None else status=='retired',data_source=data_source,kind=kind,channel_id=channel_id),sensor_view,'sensor_code'))

    @router.get('/sensors/{sensor_id}')
    def sensor(tenant_id:UUID,sensor_id:UUID,request:Request):
        with scope(request,tenant_id,'registry.read') as r:
            return result(request,sensor=sensor_view(r.get('sensors',sensor_id)))

    @router.patch('/sensors/{sensor_id}')
    def update_sensor(tenant_id:UUID,sensor_id:UUID,payload:SensorPatch,request:Request):
        with scope(request,tenant_id,'registry.manage',True) as r:
            return result(request,sensor=r.patch_sensor(sensor_id,payload))

    @router.post('/machines/{machine_id}/installations',status_code=201)
    def install(tenant_id:UUID,machine_id:UUID,payload:InstallationCreate,request:Request):
        with scope(request,tenant_id,'installations.manage',True) as r:
            return result(request,installation=r.install(machine_id,payload))

    @router.get('/machines/{machine_id}/installations')
    def installations(tenant_id:UUID,machine_id:UUID,request:Request,
                      limit:Annotated[int,Query(ge=1,le=100)]=25,offset:Annotated[int,Query(ge=0,le=100000)]=0,
                      open_only:bool=False):
        with scope(request,tenant_id,'registry.read') as r:
            r.get('machines',machine_id)
            t=r.repo._table('installations')
            query=select(t).where(t.c.tenant_id==tenant_id,t.c.machine_id==machine_id)
            if open_only: query=query.where(t.c.valid_to.is_(None))
            rows=r.s.execute(query.order_by(t.c.valid_from,t.c.id).limit(limit+1).offset(offset)).mappings().all()
            return result(request,items=[installation_view(row) for row in rows[:limit]],next_offset=offset+limit if len(rows)>limit else None)

    @router.post('/installations/{installation_id}/remove')
    def remove(tenant_id:UUID,installation_id:UUID,payload:InstallationRemove,request:Request):
        with scope(request,tenant_id,'installations.manage',True) as r:
            return result(request,installation=r.remove(installation_id,payload))
    return router
