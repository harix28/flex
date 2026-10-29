"""Pydantic schemas and types for maintenance work orders, approval workflow, and notes."""
from datetime import datetime, date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

WorkOrderStatus = Literal['draft', 'approved', 'in_progress', 'blocked', 'completed', 'cancelled']
WorkOrderPriority = Literal['urgent', 'high', 'medium', 'low', 'unknown']
WorkOrderOrigin = Literal['prediction', 'manual']
WorkOrderTransitionAction = Literal['approve', 'start', 'block', 'resume', 'complete', 'cancel']

PREDICTION_DISCLAIMER_TEMPLATE = (
    "Review the engine's sensor trends and maintenance records. "
    "The experimental model estimates remaining life in operating cycles. "
    "A qualified person must determine inspection and maintenance actions."
)


class EvidenceSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    origin: WorkOrderOrigin
    prediction_id: UUID | None = None
    model_version: str | None = None
    model_digest: str | None = None
    bundle_digest: str | None = None
    stream_id: UUID | None = None
    cutoff_cycle: int | None = None
    rul_cycles: float | None = None
    rul_units: str = 'cycles'
    prediction_status: str | None = None
    release_status: str | None = None
    policy_version: str | None = None
    snapshot_priority_band: str | None = None
    disclaimer: str = Field(default=PREDICTION_DISCLAIMER_TEMPLATE)


class WorkOrderCreateManual(BaseModel):
    model_config = ConfigDict(extra='forbid')
    machine_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    priority: WorkOrderPriority = 'medium'
    due_date: date | None = None
    planned_date: date | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class WorkOrderCreateFromPrediction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: WorkOrderPriority | None = None
    due_date: date | None = None
    planned_date: date | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, description="Expected concurrency version")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    priority: WorkOrderPriority | None = None
    due_date: date | None = None
    planned_date: date | None = None


class WorkOrderAssign(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, description="Expected concurrency version")
    technician_id: UUID
    reason: str | None = Field(default=None, max_length=1000)


class WorkOrderTransition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, description="Expected concurrency version")
    action: WorkOrderTransitionAction
    reason: str | None = Field(default=None, max_length=1000)
    completion_summary: str | None = Field(default=None, max_length=4000)


class WorkOrderNoteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(strict=True, ge=1, description='Expected concurrency version')
    note_text: str = Field(min_length=1, max_length=2000)


class WorkOrderView(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: UUID
    tenant_id: UUID
    work_order_number: str
    machine_id: UUID
    asset_code: str | None = None
    machine_name: str | None = None
    title: str
    description: str
    status: WorkOrderStatus
    priority: WorkOrderPriority
    assigned_technician_id: UUID | None = None
    assigned_technician_name: str | None = None
    planned_date: date | None = None
    due_date: date | None = None
    created_by_id: UUID
    created_by_name: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    completion_summary: str | None = None
    completed_at: datetime | None = None
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    block_reason: str | None = None
    blocked_at: datetime | None = None
    evidence: EvidenceSnapshot
    is_evidence_outdated: bool = False
    latest_observation_cycle: int | None = None
    already_active: bool = False
    idempotency_replayed: bool = False


class WorkOrderTransitionView(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: UUID
    work_order_id: UUID
    from_status: str
    to_status: str
    actor_id: UUID
    actor_name: str | None = None
    reason: str | None = None
    created_at: datetime


class WorkOrderAssignmentView(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: UUID
    work_order_id: UUID
    previous_assignee_id: UUID | None = None
    previous_assignee_name: str | None = None
    new_assignee_id: UUID
    new_assignee_name: str | None = None
    assigned_by_id: UUID
    assigned_by_name: str | None = None
    reason: str | None = None
    created_at: datetime


class WorkOrderNoteView(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: UUID
    work_order_id: UUID
    author_id: UUID
    author_name: str | None = None
    note_text: str
    created_at: datetime


class WorkOrderHistoryView(BaseModel):
    model_config = ConfigDict(extra='ignore')
    work_order: WorkOrderView
    transitions: list[WorkOrderTransitionView]
    assignments: list[WorkOrderAssignmentView]
    notes: list[WorkOrderNoteView]


class WorkOrderListResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    items: list[WorkOrderView]
    total: int
    limit: int
    offset: int
    request_id: UUID | None = None
