"""REST API endpoints for maintenance planning, parts inventory, and technician rosters."""
from contextlib import contextmanager
from uuid import UUID
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from sentinel.auth.context import AuthContext
from sentinel.planning import inventory, shifts, service


class StockUpdate(BaseModel):
    stock_qty: int = Field(ge=0, description="New stock quantity in warehouse")


class DutyUpdate(BaseModel):
    is_on_duty: bool = Field(description="Whether technician is on duty")


def planning_router(database, settings) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}/planning', tags=['Maintenance Planning'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'work_orders.read'):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.get('/inventory')
    def get_inventory(organization_id: UUID, request: Request):
        """Lists warehouse spare parts, bin locations, and stock levels."""
        with scoped_tenant(request, organization_id, 'work_orders.read'):
            return {'items': inventory.get_tenant_inventory(organization_id)}

    @router.patch('/inventory/{part_number}')
    def update_stock(organization_id: UUID, part_number: str, body: StockUpdate, request: Request):
        """Updates warehouse stock level for a part."""
        with scoped_tenant(request, organization_id, 'work_orders.approve'):
            res = inventory.update_part_stock(organization_id, part_number, body.stock_qty)
            if not res:
                raise HTTPException(404, 'part_not_found')
            return {'part': res}

    @router.get('/shifts')
    def get_shifts(organization_id: UUID, request: Request):
        """Lists technician shift schedules, qualifications, and on-duty status."""
        with scoped_tenant(request, organization_id, 'work_orders.read'):
            return {'items': shifts.get_tenant_roster(organization_id)}

    @router.patch('/shifts/{technician_id}')
    def update_technician_duty(organization_id: UUID, technician_id: str, body: DutyUpdate, request: Request):
        """Updates technician duty status."""
        with scoped_tenant(request, organization_id, 'work_orders.approve'):
            res = shifts.update_technician_duty(organization_id, technician_id, body.is_on_duty)
            if not res:
                raise HTTPException(404, 'technician_not_found')
            return {'technician': res}

    @router.get('/work-orders/{work_order_id}/readiness')
    def get_work_order_readiness(organization_id: UUID, work_order_id: UUID, request: Request):
        """Evaluates warehouse parts availability and qualified staff readiness for a work order."""
        with scoped_tenant(request, organization_id, 'work_orders.read') as (s, actor):
            try:
                assessment = service.evaluate_work_order_readiness(s, organization_id, work_order_id)
                return {'readiness': assessment}
            except ValueError as e:
                raise HTTPException(404, str(e))

    return router
