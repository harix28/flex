"""REST API endpoints for aircraft engine audit dossiers and investigation packets."""
from contextlib import contextmanager
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import text
from sentinel.auth.context import AuthContext
from sentinel.audit.dossier import generate_audit_dossier_pdf
from sentinel.registry import service as registry_service
from sentinel.ingestion import service as ingestion_service
from sentinel.predictions import service as predictions_service
from sentinel.work_orders import service as work_orders_service


def audit_router(database, settings) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}', tags=['Audit & Compliance'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'predictions.read'):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.get('/machines/{machine_id}/audit-dossier')
    def get_audit_dossier(
        organization_id: UUID,
        machine_id: UUID,
        request: Request
    ):
        """Generates a downloadable, cryptographic PDF audit dossier for an engine asset."""
        with scoped_tenant(request, organization_id, 'predictions.read') as (s, actor):
            # 1. Fetch Machine
            reg = registry_service.Registry(s, organization_id, actor['user_id'], getattr(request.state, 'request_id', ''))
            machine_row = reg.get('machines', machine_id)
            machine = registry_service.machine_view(machine_row)

            # 2. Fetch Data Quality
            try:
                dq = ingestion_service.quality(s, organization_id, machine_id, 1, None)
            except Exception:
                dq = {
                    'first_cycle': None,
                    'latest_cycle': None,
                    'observation_count': 0,
                    'is_contiguous': True,
                    'gaps': [],
                }

            # 3. Fetch Observations (up to 300 cycles for the chart)
            stream = ingestion_service.get_stream(s, organization_id, machine_id)
            observations = []
            if stream:
                rows = s.execute(text("""
                    SELECT cycle, settings, sensors FROM replay_observations
                    WHERE tenant_id = :t AND machine_id = :m AND stream_id = :s
                    ORDER BY cycle ASC LIMIT 300
                """), {'t': organization_id, 'm': machine_id, 's': stream['id']}).mappings().all()
                observations = [dict(r) for r in rows]

            # 4. Fetch Latest Prediction
            try:
                pred = predictions_service.get_latest_prediction(s, organization_id, machine_id)
            except Exception:
                pred = None

            # 5. Fetch Related Work Orders
            try:
                wo_res = work_orders_service.list_work_orders(s, organization_id, machine_id=machine_id, limit=5)
                work_orders = wo_res.get('items', [])
            except Exception:
                work_orders = []

            # Generate PDF
            pdf_bytes = generate_audit_dossier_pdf(
                machine_code=machine['asset_code'],
                machine_id=str(machine['id']),
                tenant_id=str(organization_id),
                source_binding=machine.get('source_binding', {}),
                data_quality=dq,
                latest_prediction=pred,
                observations=observations,
                related_work_orders=work_orders,
            )

            safe_code = machine['asset_code'].replace(' ', '_').replace('/', '_')
            filename = f"audit_dossier_{safe_code}.pdf"

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Request-Id": getattr(request.state, 'request_id', ''),
                }
            )

    return router

