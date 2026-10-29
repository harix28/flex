"""Service layer for maintenance work orders, state transitions, assignments, notes, and evidence provenance."""
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sentinel.auth.permissions import PERMISSIONS, permits
from .schemas import (
    WorkOrderStatus,
    WorkOrderPriority,
    WorkOrderTransitionAction,
    PREDICTION_DISCLAIMER_TEMPLATE,
)

MAX_PAGE_LIMIT = 100

HTML_TAG_PATTERN = re.compile(r'<[^>]+>')


def sanitize_plain_text(val: str, field_name: str = "text") -> str:
    """Ensures input is plain text and rejects or strips executable HTML markup."""
    if not val:
        return ""
    if HTML_TAG_PATTERN.search(val):
        raise HTTPException(400, f"HTML markup is not permitted in {field_name}")
    return val.strip()


def compute_payload_hash(payload: dict) -> str:
    """Computes deterministic SHA-256 hex digest of a canonical payload dictionary."""
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def next_work_order_number(s, tenant: UUID) -> str:
    """Monotonically increments organization-scoped work order sequence and formats human-readable code."""
    row = s.execute(text("""
        INSERT INTO work_order_counters (tenant_id, last_number)
        VALUES (:t, 1)
        ON CONFLICT (tenant_id) DO UPDATE SET last_number = work_order_counters.last_number + 1
        RETURNING last_number
    """), dict(t=tenant)).mappings().one()
    return f"WO-{row['last_number']:05d}"


def record_audit(s, tenant: UUID, actor_id: UUID, action: str, target_id: UUID, request_id: UUID | None = None):
    """Appends an immutable audit event to auth_audit_events."""
    req_id = request_id if request_id is not None else uuid4()
    s.execute(text("""
        INSERT INTO auth_audit_events (id, action, tenant_id, actor_id, target_type, target_id, request_id, created_at)
        VALUES (:id, :action, :tenant, :actor, 'work_order', :target, :req, clock_timestamp())
    """), dict(
        id=uuid4(),
        action=action,
        tenant=tenant,
        actor=actor_id,
        target=target_id,
        req=req_id,
    ))


def get_work_order_raw(s, tenant: UUID, work_order_id: UUID, for_update: bool = False):
    query = """
        SELECT w.*,
               m.asset_code, m.name AS machine_name,
               u_assign.display_name AS assigned_technician_name,
               u_create.display_name AS created_by_name
        FROM work_orders w
        JOIN machines m ON m.id = w.machine_id AND m.tenant_id = w.tenant_id
        JOIN users u_create ON u_create.id = w.created_by_id
        LEFT JOIN users u_assign ON u_assign.id = w.assigned_technician_id
        WHERE w.tenant_id = :t AND w.id = :id
    """
    if for_update:
        query += " FOR UPDATE OF w"
    row = s.execute(text(query), dict(t=tenant, id=work_order_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, 'not_found')
    return row


def build_work_order_view(s, row, already_active: bool = False, idempotency_replayed: bool = False) -> dict:
    d = dict(row)
    d['already_active'] = already_active
    d['idempotency_replayed'] = idempotency_replayed

    origin = d['origin']
    evidence = {
        'origin': origin,
        'prediction_id': d.get('prediction_id'),
        'model_version': d.get('model_version'),
        'model_digest': d.get('model_digest'),
        'bundle_digest': d.get('bundle_digest'),
        'stream_id': d.get('stream_id'),
        'cutoff_cycle': d.get('cutoff_cycle'),
        'rul_cycles': d.get('rul_cycles'),
        'rul_units': 'cycles',
        'prediction_status': d.get('prediction_status'),
        'release_status': d.get('release_status'),
        'policy_version': d.get('policy_version'),
        'snapshot_priority_band': d.get('snapshot_priority_band'),
        'disclaimer': PREDICTION_DISCLAIMER_TEMPLATE if origin == 'prediction' else "Manual maintenance draft created by authorized staff.",
    }
    d['evidence'] = evidence

    is_outdated = False
    latest_obs_cycle = None
    if origin == 'prediction' and d.get('stream_id'):
        max_row = s.execute(text("""
            SELECT MAX(cycle) AS max_cycle
            FROM replay_observations
            WHERE tenant_id = :t AND stream_id = :s
        """), dict(t=d['tenant_id'], s=d['stream_id'])).mappings().one_or_none()
        latest_obs_cycle = max_row['max_cycle'] if max_row and max_row['max_cycle'] is not None else d.get('cutoff_cycle')
        if latest_obs_cycle and d.get('cutoff_cycle') and latest_obs_cycle > d['cutoff_cycle']:
            is_outdated = True

    if origin == 'prediction':
        latest_prediction = s.execute(text('''SELECT id FROM predictions
            WHERE tenant_id=:t AND machine_id=:m
            ORDER BY requested_cutoff_cycle DESC, created_at DESC, id DESC LIMIT 1'''),
            dict(t=d['tenant_id'], m=d['machine_id'])).scalar_one_or_none()
        is_outdated = is_outdated or latest_prediction != d['prediction_id']

    d['is_evidence_outdated'] = is_outdated
    d['latest_observation_cycle'] = latest_obs_cycle
    return d


def validate_assignee(s, tenant: UUID, technician_id: UUID) -> dict:
    """Validates that assignee is an active user with active membership and documented technician execution permission."""
    row = s.execute(text("""
        SELECT u.id, u.display_name, m.roles
        FROM memberships m
        JOIN users u ON u.id = m.user_id
        WHERE m.tenant_id = :t AND m.user_id = :uid AND m.active AND u.active
    """), dict(t=tenant, uid=technician_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(400, "Assignee must be an active member in this organization")
    roles = row['roles']
    has_exec = any('work_orders.execute' in PERMISSIONS.get(r, ()) for r in roles)
    if not has_exec:
        raise HTTPException(400, "Assignee must hold technician execution permission")
    return dict(row)


def find_active_prediction_work_order(s, tenant: UUID, machine_id: UUID):
    """Finds an existing active prediction work order for a machine."""
    row = s.execute(text("""
        SELECT id FROM work_orders
        WHERE tenant_id = :t AND machine_id = :m AND origin = 'prediction'
          AND status IN ('draft', 'approved', 'in_progress', 'blocked')
        LIMIT 1
    """), dict(t=tenant, m=machine_id)).mappings().one_or_none()
    if row:
        return get_work_order_raw(s, tenant, row['id'])
    return None


def create_draft_from_prediction(
    s,
    tenant: UUID,
    prediction_id: UUID,
    actor_id: UUID,
    title: str | None = None,
    description: str | None = None,
    priority: WorkOrderPriority | None = None,
    due_date=None,
    planned_date=None,
    idempotency_key: str | None = None,
    request_id: UUID | None = None,
) -> dict:
    """Creates a draft work order from an available, current prediction, preserving immutable evidence."""
    # Check idempotency first if key supplied
    if idempotency_key:
        idemp_payload = {
            'action': 'prediction_draft',
            'prediction_id': str(prediction_id),
            'title': title,
            'description': description,
            'priority': priority,
            'due_date': str(due_date) if due_date else None,
            'planned_date': str(planned_date) if planned_date else None,
        }
        req_hash = compute_payload_hash(idemp_payload)
        idemp_row = s.execute(text("""
            SELECT request_hash, work_order_id FROM work_order_idempotency
            WHERE tenant_id = :t AND idempotency_key = :k
        """), dict(t=tenant, k=idempotency_key)).mappings().one_or_none()
        if idemp_row:
            if idemp_row['request_hash'] != req_hash:
                raise HTTPException(409, "Idempotency key already used with different payload")
            existing = get_work_order_raw(s, tenant, idemp_row['work_order_id'])
            return build_work_order_view(s, existing, idempotency_replayed=True)

    # 1. Fetch prediction and machine
    pred_row = s.execute(text("""
        SELECT p.*, m.asset_code, m.name AS machine_name
        FROM predictions p
        JOIN machines m ON m.id = p.machine_id AND m.tenant_id = p.tenant_id
        WHERE p.tenant_id = :t AND p.id = :pid
    """), dict(t=tenant, pid=prediction_id)).mappings().one_or_none()
    if pred_row is None:
        raise HTTPException(404, "Prediction not found in this organization")

    # 2. Eligibility checks
    if pred_row['status'] != 'available':
        raise HTTPException(400, "Cannot create work order: prediction status is unavailable")

    # Check if prediction is outdated under Phase 6 causal rules
    if pred_row['stream_id']:
        max_row = s.execute(text("""
            SELECT MAX(cycle) AS max_cycle
            FROM replay_observations
            WHERE tenant_id = :t AND stream_id = :s
        """), dict(t=tenant, s=pred_row['stream_id'])).mappings().one_or_none()
        if max_row and max_row['max_cycle'] and max_row['max_cycle'] > pred_row['observed_cutoff_cycle']:
            raise HTTPException(400, "Cannot create work order: prediction is outdated by newer observations")

    # 3. Deduplication check: return existing active work order if present
    existing_active = find_active_prediction_work_order(s, tenant, pred_row['machine_id'])
    if existing_active:
        return build_work_order_view(s, existing_active, already_active=True)

    # 4. Prepare draft fields
    wo_num = next_work_order_number(s, tenant)
    wo_id = uuid4()
    actual_title = title.strip() if title and title.strip() else f"Maintenance review for {pred_row['asset_code']} (Cycle {pred_row['requested_cutoff_cycle']})"
    actual_desc = description.strip() if description and description.strip() else PREDICTION_DISCLAIMER_TEMPLATE
    actual_title = sanitize_plain_text(actual_title, "title")
    actual_desc = sanitize_plain_text(actual_desc, "description")
    actual_priority = priority if priority else pred_row['priority_band']
    if actual_priority not in ('urgent', 'high', 'medium', 'low', 'unknown'):
        actual_priority = 'medium'

    try:
        s.execute(text("""
            INSERT INTO work_orders (
                id, tenant_id, work_order_number, machine_id, title, description,
                status, priority, created_by_id, planned_date, due_date, version,
                origin, prediction_id, model_version, model_digest, bundle_digest,
                stream_id, cutoff_cycle, rul_cycles, prediction_status, release_status,
                policy_version, snapshot_priority_band, created_at, updated_at
            ) VALUES (
                :id, :tenant, :num, :machine, :title, :desc,
                'draft', :priority, :actor, :planned, :due, 1,
                'prediction', :pid, :mv, :md, :bd,
                :stream, :cutoff, :rul, :status, :release,
                :policy, :band, clock_timestamp(), clock_timestamp()
            )
        """), dict(
            id=wo_id,
            tenant=tenant,
            num=wo_num,
            machine=pred_row['machine_id'],
            title=actual_title,
            desc=actual_desc,
            priority=actual_priority,
            actor=actor_id,
            planned=planned_date,
            due=due_date,
            pid=pred_row['id'],
            mv=pred_row['model_version'],
            md=pred_row['model_digest'],
            bd=pred_row['bundle_digest'],
            stream=pred_row['stream_id'],
            cutoff=pred_row['requested_cutoff_cycle'],
            rul=pred_row['rul_cycles'],
            status=pred_row['status'],
            release=pred_row['release_status'],
            policy=pred_row['policy_version'],
            band=pred_row['priority_band'],
        ))
    except IntegrityError as e:
        # Race condition on partial unique index: another request created active work order concurrently
        s.rollback()
        existing_active = find_active_prediction_work_order(s, tenant, pred_row['machine_id'])
        if existing_active:
            return build_work_order_view(s, existing_active, already_active=True)
        raise

    # Initial transition entry
    s.execute(text("""
        INSERT INTO work_order_transitions (id, tenant_id, work_order_id, from_status, to_status, actor_id, reason, created_at)
        VALUES (:id, :t, :wo, 'draft', 'draft', :actor, 'Initial draft created from prediction snapshot', clock_timestamp())
    """), dict(id=uuid4(), t=tenant, wo=wo_id, actor=actor_id))

    # Audit log
    record_audit(s, tenant, actor_id, 'work_order_created', wo_id, request_id)

    # Record idempotency if key was provided
    if idempotency_key:
        s.execute(text("""
            INSERT INTO work_order_idempotency (tenant_id, idempotency_key, request_hash, work_order_id, created_at)
            VALUES (:t, :k, :h, :wo, clock_timestamp())
        """), dict(t=tenant, k=idempotency_key, h=req_hash, wo=wo_id))

    created = get_work_order_raw(s, tenant, wo_id)
    return build_work_order_view(s, created)


def create_manual_draft(
    s,
    tenant: UUID,
    machine_id: UUID,
    actor_id: UUID,
    title: str,
    description: str,
    priority: WorkOrderPriority = 'medium',
    due_date=None,
    planned_date=None,
    idempotency_key: str | None = None,
    request_id: UUID | None = None,
) -> dict:
    """Creates a manual draft work order without model prediction dependencies."""
    if idempotency_key:
        idemp_payload = {
            'action': 'manual_draft',
            'machine_id': str(machine_id),
            'title': title,
            'description': description,
            'priority': priority,
            'due_date': str(due_date) if due_date else None,
            'planned_date': str(planned_date) if planned_date else None,
        }
        req_hash = compute_payload_hash(idemp_payload)
        idemp_row = s.execute(text("""
            SELECT request_hash, work_order_id FROM work_order_idempotency
            WHERE tenant_id = :t AND idempotency_key = :k
        """), dict(t=tenant, k=idempotency_key)).mappings().one_or_none()
        if idemp_row:
            if idemp_row['request_hash'] != req_hash:
                raise HTTPException(409, "Idempotency key already used with different payload")
            existing = get_work_order_raw(s, tenant, idemp_row['work_order_id'])
            return build_work_order_view(s, existing, idempotency_replayed=True)

    # Verify machine belongs to tenant
    mach = s.execute(text("SELECT id FROM machines WHERE tenant_id=:t AND id=:m"), dict(t=tenant, m=machine_id)).mappings().one_or_none()
    if mach is None:
        raise HTTPException(404, "Machine not found in this organization")

    actual_title = sanitize_plain_text(title, "title")
    actual_desc = sanitize_plain_text(description, "description")
    if len(actual_title) < 3 or len(actual_title) > 200:
        raise HTTPException(400, "Title must be between 3 and 200 characters")
    if len(actual_desc) < 1 or len(actual_desc) > 4000:
        raise HTTPException(400, "Description must be between 1 and 4000 characters")

    wo_num = next_work_order_number(s, tenant)
    wo_id = uuid4()

    s.execute(text("""
        INSERT INTO work_orders (
            id, tenant_id, work_order_number, machine_id, title, description,
            status, priority, created_by_id, planned_date, due_date, version,
            origin, created_at, updated_at
        ) VALUES (
            :id, :tenant, :num, :machine, :title, :desc,
            'draft', :priority, :actor, :planned, :due, 1,
            'manual', clock_timestamp(), clock_timestamp()
        )
    """), dict(
        id=wo_id,
        tenant=tenant,
        num=wo_num,
        machine=machine_id,
        title=actual_title,
        desc=actual_desc,
        priority=priority,
        actor=actor_id,
        planned=planned_date,
        due=due_date,
    ))

    # Initial transition entry
    s.execute(text("""
        INSERT INTO work_order_transitions (id, tenant_id, work_order_id, from_status, to_status, actor_id, reason, created_at)
        VALUES (:id, :t, :wo, 'draft', 'draft', :actor, 'Initial manual draft created', clock_timestamp())
    """), dict(id=uuid4(), t=tenant, wo=wo_id, actor=actor_id))

    # Audit log
    record_audit(s, tenant, actor_id, 'work_order_created', wo_id, request_id)

    if idempotency_key:
        s.execute(text("""
            INSERT INTO work_order_idempotency (tenant_id, idempotency_key, request_hash, work_order_id, created_at)
            VALUES (:t, :k, :h, :wo, clock_timestamp())
        """), dict(t=tenant, k=idempotency_key, h=req_hash, wo=wo_id))

    created = get_work_order_raw(s, tenant, wo_id)
    return build_work_order_view(s, created)


def assign_technician(
    s,
    tenant: UUID,
    work_order_id: UUID,
    actor_id: UUID,
    technician_id: UUID,
    expected_version: int,
    reason: str | None = None,
    request_id: UUID | None = None,
) -> dict:
    """Assigns or reassigns an open work order to an eligible technician with optimistic locking."""
    wo = get_work_order_raw(s, tenant, work_order_id, for_update=True)
    if wo['status'] in ('completed', 'cancelled'):
        raise HTTPException(400, "Cannot assign a completed or cancelled work order")

    if wo['version'] != expected_version:
        raise HTTPException(409, 'version_conflict')

    # Validate assignee eligibility
    validate_assignee(s, tenant, technician_id)

    prev_assignee = wo['assigned_technician_id']
    clean_reason = sanitize_plain_text(reason, "reason") if reason else None

    res = s.execute(text("""
        UPDATE work_orders
        SET assigned_technician_id = :new_tech,
            version = version + 1,
            updated_at = clock_timestamp()
        WHERE id = :id AND tenant_id = :t AND version = :v
        RETURNING *
    """), dict(new_tech=technician_id, id=work_order_id, t=tenant, v=expected_version)).mappings().one_or_none()

    if res is None:
        raise HTTPException(409, "version_conflict")

    # Record assignment history
    s.execute(text("""
        INSERT INTO work_order_assignments (
            id, tenant_id, work_order_id, previous_assignee_id, new_assignee_id, assigned_by_id, reason, created_at
        ) VALUES (
            :id, :t, :wo, :prev, :new, :actor, :reason, clock_timestamp()
        )
    """), dict(
        id=uuid4(),
        t=tenant,
        wo=work_order_id,
        prev=prev_assignee,
        new=technician_id,
        actor=actor_id,
        reason=clean_reason,
    ))

    record_audit(s, tenant, actor_id, 'work_order_assigned', work_order_id, request_id)

    updated = get_work_order_raw(s, tenant, work_order_id)
    return build_work_order_view(s, updated)


def transition_work_order(
    s,
    tenant: UUID,
    work_order_id: UUID,
    actor_id: UUID,
    actor_roles: list[str],
    action: WorkOrderTransitionAction,
    expected_version: int,
    reason: str | None = None,
    completion_summary: str | None = None,
    request_id: UUID | None = None,
) -> dict:
    """Executes state machine transitions enforcing permission gates, reason requirements, and optimistic locking."""
    wo = get_work_order_raw(s, tenant, work_order_id, for_update=True)
    current_status = wo['status']

    if current_status in ('completed', 'cancelled'):
        raise HTTPException(400, f"Work order is in terminal state '{current_status}' and cannot transition")

    if wo['version'] != expected_version:
        raise HTTPException(409, 'version_conflict')

    clean_reason = sanitize_plain_text(reason, "reason") if reason else None
    clean_summary = sanitize_plain_text(completion_summary, "completion_summary") if completion_summary else None

    target_status = None
    audit_action = 'work_order_transitioned'

    # Re-evaluate execution authorization on every action, including block/complete.
    # Membership roles are fetched by AuthContext after the tenant mutation lock.
    if action in ('start', 'block', 'resume', 'complete'):
        manager = any(r in ('admin', 'plant_manager') for r in actor_roles)
        if not manager and (wo['assigned_technician_id'] != actor_id or
                            not permits(actor_roles, 'work_orders.execute')):
            raise HTTPException(403, 'forbidden')
        if wo['assigned_technician_id'] is None:
            raise HTTPException(400, 'assignee_ineligible')
        try:
            validate_assignee(s, tenant, wo['assigned_technician_id'])
        except HTTPException:
            raise HTTPException(409, 'assignee_ineligible') from None

    # Evaluate allowed transitions and permissions
    if action == 'approve':
        if current_status != 'draft':
            raise HTTPException(400, f"Cannot approve work order in status '{current_status}'")
        if not any('work_orders.approve' in PERMISSIONS.get(r, ()) for r in actor_roles):
            raise HTTPException(403, "Only plant managers and admins can approve work orders")
        # The tenant mutation lock also serializes replay/prediction writes. Check
        # freshness here, not only when the draft was created or last displayed.
        if build_work_order_view(s, wo)['is_evidence_outdated']:
            raise HTTPException(409, 'outdated_evidence')
        target_status = 'approved'
        audit_action = 'work_order_approved'

    elif action == 'start':
        if current_status not in ('approved', 'blocked'):
            raise HTTPException(400, f"Cannot start work order in status '{current_status}'")
        if wo['assigned_technician_id'] is None:
            raise HTTPException(400, "Cannot start work without an assigned technician")
        # Validate that current assignee is still active
        validate_assignee(s, tenant, wo['assigned_technician_id'])
        # If actor has technician role only, must be the assigned technician
        is_assigned_tech = (wo['assigned_technician_id'] == actor_id)
        is_manager_or_admin = any(r in ('admin', 'plant_manager') for r in actor_roles)
        if not (is_assigned_tech or is_manager_or_admin):
            raise HTTPException(403, "Only the assigned technician or manager can start this work order")
        target_status = 'in_progress'

    elif action == 'block':
        if current_status != 'in_progress':
            raise HTTPException(400, f"Cannot block work order in status '{current_status}'")
        if not clean_reason or len(clean_reason) < 3:
            raise HTTPException(400, "A valid reason (min 3 characters) is required when blocking work")
        is_assigned_tech = (wo['assigned_technician_id'] == actor_id)
        is_manager_or_admin = any(r in ('admin', 'plant_manager') for r in actor_roles)
        if not (is_assigned_tech or is_manager_or_admin):
            raise HTTPException(403, "Only the assigned technician or manager can block this work order")
        target_status = 'blocked'

    elif action == 'resume':
        if current_status != 'blocked':
            raise HTTPException(400, f"Cannot resume work order in status '{current_status}'")
        if wo['assigned_technician_id'] is None:
            raise HTTPException(400, "Cannot resume work without an assigned technician")
        validate_assignee(s, tenant, wo['assigned_technician_id'])
        is_assigned_tech = (wo['assigned_technician_id'] == actor_id)
        is_manager_or_admin = any(r in ('admin', 'plant_manager') for r in actor_roles)
        if not (is_assigned_tech or is_manager_or_admin):
            raise HTTPException(403, "Only the assigned technician or manager can resume this work order")
        target_status = 'in_progress'

    elif action == 'complete':
        if current_status != 'in_progress':
            raise HTTPException(400, f"Cannot complete work order in status '{current_status}'")
        if not clean_summary or len(clean_summary) < 3:
            raise HTTPException(400, "A completion summary (min 3 characters) is required when completing work")
        is_assigned_tech = (wo['assigned_technician_id'] == actor_id)
        is_manager_or_admin = any(r in ('admin', 'plant_manager') for r in actor_roles)
        if not (is_assigned_tech or is_manager_or_admin):
            raise HTTPException(403, "Only the assigned technician or manager can complete this work order")
        target_status = 'completed'
        audit_action = 'work_order_completed'

    elif action == 'cancel':
        if current_status in ('completed', 'cancelled'):
            raise HTTPException(400, f"Cannot cancel work order in status '{current_status}'")
        if not any('work_orders.cancel' in PERMISSIONS.get(r, ()) for r in actor_roles):
            raise HTTPException(403, "Only plant managers and admins can cancel work orders")
        if not clean_reason or len(clean_reason) < 3:
            raise HTTPException(400, "A valid reason (min 3 characters) is required when cancelling a work order")
        target_status = 'cancelled'
        audit_action = 'work_order_cancelled'

    else:
        raise HTTPException(400, f"Unsupported action '{action}'")

    # Update work order state
    set_clauses = ["status = :target", "version = version + 1", "updated_at = clock_timestamp()"]
    params = {
        'target': target_status,
        'id': work_order_id,
        't': tenant,
        'v': expected_version,
    }

    if target_status == 'completed':
        set_clauses.extend(["completion_summary = :summary", "completed_at = clock_timestamp()"])
        params['summary'] = clean_summary
    elif target_status == 'cancelled':
        set_clauses.extend(["cancellation_reason = :reason", "cancelled_at = clock_timestamp()"])
        params['reason'] = clean_reason
    elif target_status == 'blocked':
        set_clauses.extend(["block_reason = :reason", "blocked_at = clock_timestamp()"])
        params['reason'] = clean_reason
    elif target_status == 'in_progress' and current_status == 'blocked':
        set_clauses.extend(["block_reason = NULL", "blocked_at = NULL"])

    update_query = f"UPDATE work_orders SET {', '.join(set_clauses)} WHERE id = :id AND tenant_id = :t AND version = :v RETURNING *"
    res = s.execute(text(update_query), params).mappings().one_or_none()
    if res is None:
        raise HTTPException(409, "version_conflict")

    # Record transition history
    transition_reason = clean_reason or clean_summary or f"Action {action} performed"
    s.execute(text("""
        INSERT INTO work_order_transitions (
            id, tenant_id, work_order_id, from_status, to_status, actor_id, reason, created_at
        ) VALUES (
            :id, :t, :wo, :from_s, :to_s, :actor, :reason, clock_timestamp()
        )
    """), dict(
        id=uuid4(),
        t=tenant,
        wo=work_order_id,
        from_s=current_status,
        to_s=target_status,
        actor=actor_id,
        reason=transition_reason,
    ))

    # Audit log
    record_audit(s, tenant, actor_id, audit_action, work_order_id, request_id)

    updated = get_work_order_raw(s, tenant, work_order_id)
    return build_work_order_view(s, updated)


def update_work_order(
    s,
    tenant: UUID,
    work_order_id: UUID,
    actor_id: UUID,
    expected_version: int,
    title: str | None = None,
    description: str | None = None,
    priority: WorkOrderPriority | None = None,
    due_date=None,
    planned_date=None,
    request_id: UUID | None = None,
) -> dict:
    """Updates permitted mutable fields (title, description, priority, dates) with optimistic locking."""
    wo = get_work_order_raw(s, tenant, work_order_id, for_update=True)
    if wo['status'] in ('completed', 'cancelled'):
        raise HTTPException(400, "Cannot update a completed or cancelled work order")

    if wo['version'] != expected_version:
        raise HTTPException(409, 'version_conflict')

    set_clauses = ["version = version + 1", "updated_at = clock_timestamp()"]
    params = {'id': work_order_id, 't': tenant, 'v': expected_version}
    audit_changes = {}

    if title is not None:
        clean_title = sanitize_plain_text(title, "title")
        if len(clean_title) < 3 or len(clean_title) > 200:
            raise HTTPException(400, "Title must be between 3 and 200 characters")
        set_clauses.append("title = :title")
        params['title'] = clean_title
        audit_changes['title'] = clean_title

    if description is not None:
        clean_desc = sanitize_plain_text(description, "description")
        if len(clean_desc) < 1 or len(clean_desc) > 4000:
            raise HTTPException(400, "Description must be between 1 and 4000 characters")
        set_clauses.append("description = :desc")
        params['desc'] = clean_desc
        audit_changes['description_updated'] = True

    if priority is not None:
        if priority not in ('urgent', 'high', 'medium', 'low', 'unknown'):
            raise HTTPException(400, "Invalid priority")
        set_clauses.append("priority = :priority")
        params['priority'] = priority
        audit_changes['previous_priority'] = wo['priority']
        audit_changes['new_priority'] = priority

    if due_date is not None:
        set_clauses.append("due_date = :due")
        params['due'] = due_date
        audit_changes['due_date'] = str(due_date)

    if planned_date is not None:
        set_clauses.append("planned_date = :planned")
        params['planned'] = planned_date
        audit_changes['planned_date'] = str(planned_date)

    update_query = f"UPDATE work_orders SET {', '.join(set_clauses)} WHERE id = :id AND tenant_id = :t AND version = :v RETURNING *"
    res = s.execute(text(update_query), params).mappings().one_or_none()
    if res is None:
        raise HTTPException(409, "version_conflict")

    audit_action = 'work_order_priority_changed' if priority is not None and priority != wo['priority'] else 'work_order_updated'
    record_audit(s, tenant, actor_id, audit_action, work_order_id, request_id)

    updated = get_work_order_raw(s, tenant, work_order_id)
    return build_work_order_view(s, updated)


def add_note(s, tenant: UUID, work_order_id: UUID, author_id: UUID, actor_roles: list[str], note_text: str, expected_version: int, request_id: UUID | None = None) -> tuple[dict, int]:
    """Appends a note, version increment and audit in the same transaction."""
    wo = get_work_order_raw(s, tenant, work_order_id, for_update=True)
    if wo['version'] != expected_version:
        raise HTTPException(409, 'version_conflict')
    # If actor has only technician role, verify they are assigned
    if 'technician' in actor_roles and not any(r in ('admin', 'plant_manager') for r in actor_roles):
        if wo['assigned_technician_id'] != author_id:
            raise HTTPException(403, "Technicians can only add notes to work orders assigned to them")

    clean_note = sanitize_plain_text(note_text, "note_text")
    if len(clean_note) < 1 or len(clean_note) > 2000:
        raise HTTPException(400, "Note text must be between 1 and 2000 characters")

    new_version = s.execute(text('''UPDATE work_orders
        SET version=version+1, updated_at=clock_timestamp()
        WHERE tenant_id=:t AND id=:id AND version=:v RETURNING version'''),
        dict(t=tenant, id=work_order_id, v=expected_version)).scalar_one_or_none()
    if new_version is None:
        raise HTTPException(409, 'version_conflict')

    note_id = uuid4()
    s.execute(text("""
        INSERT INTO work_order_notes (id, tenant_id, work_order_id, author_id, note_text, created_at)
        VALUES (:id, :t, :wo, :author, :note, clock_timestamp())
    """), dict(id=note_id, t=tenant, wo=work_order_id, author=author_id, note=clean_note))

    record_audit(s, tenant, author_id, 'work_order_note_added', work_order_id, request_id)

    note_row = s.execute(text("""
        SELECT n.*, u.display_name AS author_name
        FROM work_order_notes n
        JOIN users u ON u.id = n.author_id
        WHERE n.id = :id
    """), dict(id=note_id)).mappings().one()
    return dict(note_row), new_version


def list_work_orders(
    s,
    tenant: UUID,
    machine_id: UUID | None = None,
    status: WorkOrderStatus | None = None,
    priority: WorkOrderPriority | None = None,
    technician_id: UUID | None = None,
    limit: int = 25,
    offset: int = 0,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    due_from=None,
    due_to=None,
) -> tuple[list[dict], int]:
    """Retrieves paginated, filtered work orders with stable sorting."""
    clamped_limit = min(max(1, limit), MAX_PAGE_LIMIT)
    clamped_offset = max(0, offset)

    where = ["w.tenant_id = :t"]
    params = {'t': tenant, 'lim': clamped_limit, 'off': clamped_offset}

    if machine_id:
        where.append("w.machine_id = :machine")
        params['machine'] = machine_id
    if status:
        where.append("w.status = :status")
        params['status'] = status
    if priority:
        where.append("w.priority = :priority")
        params['priority'] = priority
    if technician_id:
        where.append("w.assigned_technician_id = :tech")
        params['tech'] = technician_id

    for value in (created_from, created_to):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(422, 'invalid_date_range')
    for lower, upper in ((created_from, created_to), (due_from, due_to)):
        if lower is not None and upper is not None and lower > upper:
            raise HTTPException(422, 'invalid_date_range')
    for key, column, operator, value in (
        ('created_from', 'created_at', '>=', created_from),
        ('created_to', 'created_at', '<=', created_to),
        ('due_from', 'due_date', '>=', due_from),
        ('due_to', 'due_date', '<=', due_to),
    ):
        if value is not None:
            where.append(f"w.{column} {operator} :{key}")
            params[key] = value

    where_sql = " AND ".join(where)

    total = s.execute(text(f"SELECT COUNT(*) FROM work_orders w WHERE {where_sql}"), params).scalar_one()

    query = f"""
        SELECT w.*,
               m.asset_code, m.name AS machine_name,
               u_assign.display_name AS assigned_technician_name,
               u_create.display_name AS created_by_name
        FROM work_orders w
        JOIN machines m ON m.id = w.machine_id AND m.tenant_id = w.tenant_id
        JOIN users u_create ON u_create.id = w.created_by_id
        LEFT JOIN users u_assign ON u_assign.id = w.assigned_technician_id
        WHERE {where_sql}
        ORDER BY w.created_at DESC, w.id DESC
        LIMIT :lim OFFSET :off
    """
    rows = s.execute(text(query), params).mappings().all()
    items = [build_work_order_view(s, r) for r in rows]
    return items, total


def get_work_order_history(s, tenant: UUID, work_order_id: UUID) -> dict:
    """Retrieves full history of transitions, assignments, and notes for a work order."""
    wo = get_work_order_raw(s, tenant, work_order_id)
    wo_view = build_work_order_view(s, wo)

    transitions = s.execute(text("""
        SELECT t.*, u.display_name AS actor_name
        FROM work_order_transitions t
        JOIN users u ON u.id = t.actor_id
        WHERE t.tenant_id = :tenant AND t.work_order_id = :wo
        ORDER BY t.created_at ASC
    """), dict(tenant=tenant, wo=work_order_id)).mappings().all()

    assignments = s.execute(text("""
        SELECT a.*,
               u_prev.display_name AS previous_assignee_name,
               u_new.display_name AS new_assignee_name,
               u_by.display_name AS assigned_by_name
        FROM work_order_assignments a
        LEFT JOIN users u_prev ON u_prev.id = a.previous_assignee_id
        JOIN users u_new ON u_new.id = a.new_assignee_id
        JOIN users u_by ON u_by.id = a.assigned_by_id
        WHERE a.tenant_id = :tenant AND a.work_order_id = :wo
        ORDER BY a.created_at ASC
    """), dict(tenant=tenant, wo=work_order_id)).mappings().all()

    notes = s.execute(text("""
        SELECT n.*, u.display_name AS author_name
        FROM work_order_notes n
        JOIN users u ON u.id = n.author_id
        WHERE n.tenant_id = :tenant AND n.work_order_id = :wo
        ORDER BY n.created_at ASC
    """), dict(tenant=tenant, wo=work_order_id)).mappings().all()

    return {
        'work_order': wo_view,
        'transitions': [dict(t) for t in transitions],
        'assignments': [dict(a) for a in assignments],
        'notes': [dict(n) for n in notes],
    }
