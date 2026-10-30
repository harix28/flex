"""REST API endpoints for tenant-scoped alert notifications and webhooks."""
from contextlib import contextmanager
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field
from fastapi import APIRouter, HTTPException, Request
from sentinel.auth.context import AuthContext
from sentinel.notifications import dispatcher


class WebhookCreate(BaseModel):
    url: str = Field(description="Target HTTPS/HTTP webhook URL")
    secret: str = Field(min_length=8, description="Shared secret for HMAC-SHA256 signature verification")
    events: list[str] = Field(default=["alert.urgent", "alert.high", "work_order.created"])
    label: str = Field(default="Main Alert Webhook")


class TestNotification(BaseModel):
    event_type: str = Field(default="alert.urgent")
    message: str = Field(default="Simulated test alert: Engine NASA-FD001-TEST-76 reached URGENT threshold (RUL: 2.5 cycles)")


def notifications_router(database, settings) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}/notifications', tags=['Notifications & Alerts'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'predictions.read'):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.get('/webhooks')
    def get_webhooks(organization_id: UUID, request: Request):
        """Lists registered notification webhooks for the tenant."""
        with scoped_tenant(request, organization_id, 'predictions.read'):
            return {'items': dispatcher.list_webhooks(organization_id)}

    @router.post('/webhooks')
    def create_webhook(organization_id: UUID, body: WebhookCreate, request: Request):
        """Registers a new outbound notification webhook for the tenant."""
        with scoped_tenant(request, organization_id, 'predictions.create'):
            res = dispatcher.register_webhook(
                tenant_id=organization_id,
                url=str(body.url),
                secret=body.secret,
                events=body.events,
                label=body.label
            )
            return {'webhook': res}

    @router.delete('/webhooks/{webhook_id}')
    def remove_webhook(organization_id: UUID, webhook_id: str, request: Request):
        """Deletes a registered notification webhook."""
        with scoped_tenant(request, organization_id, 'predictions.create'):
            deleted = dispatcher.delete_webhook(organization_id, webhook_id)
            if not deleted:
                raise HTTPException(404, 'webhook_not_found')
            return {'status': 'deleted', 'webhook_id': webhook_id}

    @router.post('/test')
    def trigger_test_notification(organization_id: UUID, body: TestNotification, request: Request):
        """Dispatches an immediate signed test notification event to all registered webhooks."""
        with scoped_tenant(request, organization_id, 'predictions.create'):
            result = dispatcher.dispatch_event(
                tenant_id=organization_id,
                event_type=body.event_type,
                payload={'message': body.message, 'test': True},
                force=True
            )
            return {'result': result}

    @router.get('/history')
    def get_history(organization_id: UUID, request: Request):
        """Retrieves recent notification delivery logs for audit."""
        with scoped_tenant(request, organization_id, 'predictions.read'):
            return {'items': dispatcher.get_dispatch_history(organization_id)}

    return router

