"""Pydantic schemas for persistent predictions and maintenance priority endpoints."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .policy import PriorityBand

MAX_CYCLE = 2147483647


class PredictionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cutoff_cycle: int | None = Field(default=None, ge=1, le=MAX_CYCLE)


class PredictionRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    tenant_id: UUID
    machine_id: UUID
    stream_id: UUID | None = None
    actor_id: UUID
    request_id: UUID
    status: str
    reason: str | None = None
    requested_cutoff_cycle: int
    observed_cutoff_cycle: int | None = None
    input_start_cycle: int | None = None
    input_end_cycle: int | None = None
    input_window_start_cycle: int | None = None
    input_window_end_cycle: int | None = None
    input_observation_count: int
    input_digest: str
    model_version: str
    model_digest: str
    bundle_digest: str
    inference_version: int = 1
    feature_schema_version: int = 1
    rul_cycles: float | None = None
    rul_units: str = 'cycles'
    failure_probability: None = None
    interval: None = None
    diagnosis_basis: str = 'unavailable'
    release_status: str = 'experiment_only'
    policy_version: str
    priority_band: PriorityBand | None = None
    priority_rule: str
    created_at: datetime
    idempotency_replayed: bool = False


class LatestPredictionRecord(PredictionRecord):
    is_current: bool
    is_outdated: bool
    latest_observation_cycle: int | None = None


class PredictionListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[PredictionRecord]
    total: int
    limit: int
    offset: int
    request_id: UUID


class MaintenancePriorityItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    machine_id: UUID
    asset_code: str
    machine_name: str
    machine_type: str
    priority_band: PriorityBand
    rul_cycles: float | None = None
    rul_units: str = 'cycles'
    status: str
    reason: str | None = None
    is_current: bool
    is_outdated: bool
    prediction_cutoff_cycle: int | None = None
    latest_observation_cycle: int | None = None
    explanation: str
    prediction_id: UUID | None = None
    model_version: str | None = None
    model_digest: str | None = None
    predicted_at: datetime | None = None


class MaintenancePrioritiesResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    policy_version: str
    policy_thresholds: dict
    summary: dict[str, int]
    items: list[MaintenancePriorityItem]
    limit: int
    offset: int
    total: int
    request_id: UUID
