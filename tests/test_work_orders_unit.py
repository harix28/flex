"""Unit tests for work order schemas, validation, HTML sanitization, and deterministic hashing."""
import pytest
from pydantic import ValidationError
from uuid import uuid4
from fastapi import HTTPException
from sentinel.work_orders.schemas import (
    WorkOrderCreateManual,
    WorkOrderCreateFromPrediction,
    WorkOrderUpdate,
    WorkOrderAssign,
    WorkOrderTransition,
    WorkOrderNoteCreate,
    PREDICTION_DISCLAIMER_TEMPLATE,
)
from sentinel.work_orders.service import (
    sanitize_plain_text,
    compute_payload_hash,
)


def test_work_order_manual_create_schema():
    valid = WorkOrderCreateManual(
        machine_id=uuid4(),
        title="Check high vibration on engine",
        description="Technician reported excessive vibration during routine inspection.",
        priority="high",
    )
    assert valid.priority == "high"

    # Reject title < 3 chars
    with pytest.raises(ValidationError):
        WorkOrderCreateManual(
            machine_id=uuid4(),
            title="ab",
            description="desc",
        )

    # Reject forbidden extra fields
    with pytest.raises(ValidationError):
        WorkOrderCreateManual(
            machine_id=uuid4(),
            title="Valid title",
            description="Valid desc",
            extra_field="rejected",  # type: ignore
        )


def test_work_order_prediction_draft_schema():
    valid = WorkOrderCreateFromPrediction(
        title="Custom title",
        priority="urgent",
    )
    assert valid.priority == "urgent"

    # Reject extra fields
    with pytest.raises(ValidationError):
        WorkOrderCreateFromPrediction(
            title="Custom title",
            unsupported="disallowed",  # type: ignore
        )


def test_work_order_update_requires_version():
    valid = WorkOrderUpdate(version=2, title="Updated title", priority="low")
    assert valid.version == 2

    # Reject missing or invalid version (< 1)
    with pytest.raises(ValidationError):
        WorkOrderUpdate(version=0)


def test_work_order_assign_requires_version_and_technician():
    tech_id = uuid4()
    valid = WorkOrderAssign(version=1, technician_id=tech_id, reason="Scheduled shift")
    assert valid.technician_id == tech_id

    with pytest.raises(ValidationError):
        WorkOrderAssign(version=0, technician_id=tech_id)


def test_work_order_transition_actions():
    valid = WorkOrderTransition(version=1, action="approve")
    assert valid.action == "approve"

    valid_comp = WorkOrderTransition(version=2, action="complete", completion_summary="Replaced oil filter and recalibrated sensors.")
    assert valid_comp.completion_summary is not None

    with pytest.raises(ValidationError):
        WorkOrderTransition(version=1, action="invalid_action")  # type: ignore


def test_plain_text_sanitizer_rejects_html():
    clean = sanitize_plain_text("Normal operational note from technician.")
    assert clean == "Normal operational note from technician."

    # Rejection of various HTML tags
    with pytest.raises(HTTPException) as exc1:
        sanitize_plain_text("<script>alert('xss')</script>")
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        sanitize_plain_text("Check machine <a href='http://malicious.com'>link</a>")
    assert exc2.value.status_code == 400

    with pytest.raises(HTTPException) as exc3:
        sanitize_plain_text("Image tag <img src=x onerror=steal()>")
    assert exc3.value.status_code == 400


def test_payload_hash_determinism_and_sensitivity():
    payload_a = {'title': 'Inspect engine', 'machine_id': '687dd780-1ec1-4855-acbf-b2fa6c0cb60c', 'priority': 'high'}
    payload_b = {'priority': 'high', 'machine_id': '687dd780-1ec1-4855-acbf-b2fa6c0cb60c', 'title': 'Inspect engine'}
    assert compute_payload_hash(payload_a) == compute_payload_hash(payload_b)

    payload_c = {'title': 'Inspect engine', 'machine_id': '687dd780-1ec1-4855-acbf-b2fa6c0cb60c', 'priority': 'urgent'}
    assert compute_payload_hash(payload_a) != compute_payload_hash(payload_c)


def test_prediction_disclaimer_template_boundaries():
    assert "experimental model estimates remaining life in operating cycles" in PREDICTION_DISCLAIMER_TEMPLATE
    assert "qualified person must determine inspection and maintenance actions" in PREDICTION_DISCLAIMER_TEMPLATE
    # Must NOT invent failed component, defect, or guaranteed failure date
    for forbidden in ["bearing fault", "blade crack", "component failure", "guaranteed failure"]:
        assert forbidden not in PREDICTION_DISCLAIMER_TEMPLATE.lower()
