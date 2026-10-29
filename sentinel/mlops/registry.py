"""Model registry persistence and metadata service."""
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sentinel.mlops.verification import verify_model_bundle


def register_model(session, model_dir: Path | str, trusted_sha256: str, actor: str, reason: str | None = None) -> dict:
    """Verifies a model bundle and registers its metadata in the immutable registry."""
    if not actor or not actor.strip():
        raise ValueError("Actor must be provided for model registration")

    verified = verify_model_bundle(model_dir, trusted_sha256)
    ver = verified['model_version']

    # Check for existing registration
    row = session.execute(
        text("SELECT * FROM models WHERE model_version = :v"),
        {'v': ver}
    ).mappings().one_or_none()

    if row is not None:
        if row['bundle_digest'] == verified['bundle_digest']:
            return dict(row)
        raise ValueError(f"Model version '{ver}' is already registered with different digests")

    model_id = uuid4()
    session.execute(
        text("""INSERT INTO models (
            id, model_version, model_family, bundle_digest, model_digest, report_digest,
            feature_schema, feature_count, window_size, target_subset,
            target_machine_type, target_data_source, training_provenance,
            evaluation_metrics, registration_actor, review_status
        ) VALUES (
            :id, :ver, :family, :b_digest, :m_digest, :r_digest,
            :schema, :f_count, :w_size, :subset,
            :m_type, :d_source, :prov,
            :metrics, :actor, :review_status
        )"""),
        {
            'id': model_id,
            'ver': ver,
            'family': verified['model_family'],
            'b_digest': verified['bundle_digest'],
            'm_digest': verified['model_digest'],
            'r_digest': verified['report_digest'],
            'schema': verified['feature_schema'],
            'f_count': verified['feature_count'],
            'w_size': verified['window_size'],
            'subset': verified['target_subset'],
            'm_type': verified['target_machine_type'],
            'd_source': verified['target_data_source'],
            'prov': json.dumps(verified['training_provenance']),
            'metrics': json.dumps(verified['evaluation_metrics']),
            'actor': actor.strip(),
            'review_status': verified['review_status']
        }
    )

    # Record audit event (model_registered)
    session.execute(
        text("""INSERT INTO auth_audit_events (
            id, tenant_id, actor_id, action, target_type, target_id, request_id, details
        ) VALUES (
            gen_random_uuid(), NULL, NULL, 'model_registered', 'model', :target_id, gen_random_uuid(),
            :details
        )"""),
        {
            'target_id': model_id,
            'details': json.dumps({
                'model_version': ver,
                'bundle_digest': verified['bundle_digest'],
                'actor': actor.strip(),
                'reason': reason or 'Initial model registration'
            })
        }
    )

    created = session.execute(
        text("SELECT * FROM models WHERE id = :id"),
        {'id': model_id}
    ).mappings().one()

    return dict(created)


def get_model(session, model_version: str) -> dict | None:
    row = session.execute(
        text("SELECT * FROM models WHERE model_version = :v"),
        {'v': model_version}
    ).mappings().one_or_none()
    return dict(row) if row else None


def list_models(session, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = session.execute(
        text("SELECT * FROM models ORDER BY created_at DESC LIMIT :lim OFFSET :off"),
        {'lim': max(1, min(limit, 100)), 'off': max(0, offset)}
    ).mappings().all()
    return [dict(r) for r in rows]


def update_review_status(session, model_version: str, status: str, actor: str, reason: str) -> dict:
    valid_statuses = ('experiment_only', 'reviewed_candidate', 'rejected', 'archived')
    if status not in valid_statuses:
        raise ValueError(f"Invalid review status: {status}. Must be one of {valid_statuses}")
    if not actor or not actor.strip():
        raise ValueError("Actor must be provided")
    if not reason or len(reason.strip()) < 3:
        raise ValueError("Reason must be at least 3 characters")

    row = session.execute(
        text("SELECT * FROM models WHERE model_version = :v"),
        {'v': model_version}
    ).mappings().one_or_none()
    if row is None:
        raise ValueError(f"Model version '{model_version}' not found")

    session.execute(
        text("UPDATE models SET review_status = :s WHERE id = :id"),
        {'s': status, 'id': row['id']}
    )

    session.execute(
        text("""INSERT INTO auth_audit_events (
            id, tenant_id, actor_id, action, target_type, target_id, request_id, details
        ) VALUES (
            gen_random_uuid(), NULL, NULL, 'model_registered', 'model', :target_id, gen_random_uuid(),
            :details
        )"""),
        {
            'target_id': row['id'],
            'details': json.dumps({
                'model_version': model_version,
                'previous_status': row['review_status'],
                'new_status': status,
                'actor': actor.strip(),
                'reason': reason.strip()
            })
        }
    )

    updated = session.execute(
        text("SELECT * FROM models WHERE id = :id"),
        {'id': row['id']}
    ).mappings().one()
    return dict(updated)
