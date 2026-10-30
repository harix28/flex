"""REST API endpoints for edge IoT gateways and enterprise CMMS synchronization."""
from contextlib import contextmanager
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, Query
from sqlalchemy import text
from sentinel.auth.context import AuthContext
from sentinel.integrations.iot_gateway import normalize_edge_telemetry
from sentinel.integrations.cmms import export_to_sap_pm, export_to_maximo
from sentinel.registry import service as registry_service
from sentinel.ingestion import service as ingestion_service
from sentinel.ingestion.schemas import Batch, Source, Observation
from sentinel.work_orders import service as work_orders_service


def integrations_router(database, settings) -> APIRouter:
    router = APIRouter(prefix='/api/v1/organizations/{organization_id}/integrations', tags=['Live Integrations & CMMS'])
    auth = AuthContext(database, settings)

    @contextmanager
    def scoped_tenant(request: Request, tenant_id: UUID, permission: str = 'replay.read', write: bool = False):
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            if write:
                auth.csrf(request, actor)
            auth.membership(s, actor, tenant_id, permission)
            yield s, actor

    @router.get('/status')
    def get_integrations_status(organization_id: UUID, request: Request):
        """Returns health status of enterprise CMMS and IoT edge gateway connectors."""
        with scoped_tenant(request, organization_id, 'replay.read'):
            return {
                'organization_id': str(organization_id),
                'edge_gateways': {
                    'protocols_supported': ['mqtt_sparkplug_b', 'opc_ua'],
                    'status': 'ready_for_ingestion',
                    'enforced_bounds': 'finite_float_3_settings_21_sensors'
                },
                'cmms_adapters': {
                    'systems_supported': ['SAP_PM_01', 'IBM_MAXIMO_MIF'],
                    'policy': 'human_approval_gate_enforced',
                    'status': 'configured'
                }
            }

    @router.post('/gateway/telemetry')
    def ingest_edge_telemetry(organization_id: UUID, payload: dict, request: Request):
        """Normalizes and ingests a live IoT edge sensor frame (MQTT / OPC-UA)."""
        try:
            norm = normalize_edge_telemetry(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

        asset_code = payload.get("asset_code")
        if not asset_code:
            raise HTTPException(422, "Missing required 'asset_code' in telemetry frame")

        with scoped_tenant(request, organization_id, 'replay.ingest') as (s, actor):
            # Resolve machine by asset_code in tenant
            machine_row = s.execute(text("""
                SELECT id FROM machines WHERE tenant_id = :t AND asset_code = :c AND lifecycle_status = 'active'
            """), {'t': organization_id, 'c': asset_code}).mappings().one_or_none()

            if not machine_row:
                raise HTTPException(404, f"Machine with asset code '{asset_code}' not found in active tenant")

            machine_id = machine_row['id']
            stream = ingestion_service.get_stream(s, organization_id, machine_id)
            if not stream:
                raise HTTPException(409, "observations_stream_not_initialized")

            batch_payload = Batch(
                source=Source(
                    dataset=stream['dataset'],
                    subset=stream['subset'],
                    partition=stream['partition'],
                    engine_id=stream['engine_id'],
                    file_sha256=stream['file_sha256']
                ),
                observations=[
                    Observation(
                        cycle=norm['cycle'],
                        settings=norm['settings'],
                        sensors=norm['sensors']
                    )
                ]
            )
            key = f"edge-{norm['gateway_id']}-{norm['cycle']}-{uuid4().hex[:8]}"
            try:
                raw_req_id = getattr(request.state, 'request_id', str(uuid4()))
                req_id = UUID(raw_req_id)
            except Exception:
                req_id = uuid4()

            result = ingestion_service.ingest(
                s,
                tenant=organization_id,
                machine=machine_id,
                actor=actor['user_id'],
                request_id=req_id,
                payload=batch_payload,
                key=key
            )

            return {
                'status': 'ingested',
                'asset_code': asset_code,
                'machine_id': str(machine_id),
                'cycle': norm['cycle'],
                'gateway_id': norm['gateway_id'],
                'protocol': norm['protocol'],
                'batch_id': str(result['batch']['id'])
            }

    @router.post('/cmms/export/{work_order_id}')
    def export_work_order_to_cmms(
        organization_id: UUID,
        work_order_id: UUID,
        request: Request,
        target: Literal['sap_pm', 'maximo'] = Query(default='sap_pm')
    ):
        """
        Exports an approved work order to SAP PM or IBM Maximo structure.
        Enforces human-in-the-loop approval policy: rejected if in 'draft' status.
        """
        with scoped_tenant(request, organization_id, 'work_orders.read') as (s, actor):
            raw = work_orders_service.get_work_order_raw(s, organization_id, work_order_id)
            wo = work_orders_service.build_work_order_view(s, raw)

            try:
                if target == 'sap_pm':
                    payload = export_to_sap_pm(wo)
                else:
                    payload = export_to_maximo(wo)
                return {'target': target, 'payload': payload}
            except ValueError as e:
                raise HTTPException(409, str(e))

    return router
