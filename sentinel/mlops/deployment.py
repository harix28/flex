"""Controlled model release, deployment tracking, and rollback management."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text, event
from tempfile import NamedTemporaryFile
from sentinel.mlops.verification import verify_model_bundle

RELEASE_POINTER_FILE = Path(__file__).resolve().parents[2] / '.runtime' / 'active_release.json'


def write_atomic_release_file(payload: dict, target_path: Path | None = None):
    """Replace a complete pointer; unique temporary files avoid writer collisions."""
    target_path = target_path or RELEASE_POINTER_FILE
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=target_path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, target_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _release_lock(session):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('meridian-local-release', 0))"))


def sync_release_pointer(engine):
    """Recover the local pointer from committed audit metadata, under the release lock."""
    with engine.begin() as connection:
        _release_lock(connection)
        row = connection.execute(text("""SELECT a.details->'release_pointer' AS payload
            FROM model_deployments d JOIN auth_audit_events a
              ON a.details->>'deployment_id'=d.id::text
            WHERE d.target_environment='local' AND d.status IN ('desired','active')
              AND a.action IN ('model_deployed','model_rollback')
            ORDER BY d.created_at DESC LIMIT 1""")).mappings().first()
        if row is None or not row['payload']:
            raise ValueError('No recoverable committed release; configure a verified deployment first')
        write_atomic_release_file(row['payload'])


def _publish_after_commit(session):
    if session.in_nested_transaction():
        raise ValueError('Release configuration requires a top-level transaction')
    if session.info.get('release_publish_registered'):
        return
    session.info['release_publish_registered'] = True
    engine = session.get_bind()
    def publish(committed):
        if committed.info.pop('release_pending', False):
            sync_release_pointer(engine)
    def discard(rolled_back):
        rolled_back.info.pop('release_pending', None)
    event.listen(session, 'after_commit', publish)
    event.listen(session, 'after_rollback', discard)


def read_release_file(target_path: Path | None = None) -> dict | None:
    target_path = target_path or RELEASE_POINTER_FILE
    if not target_path.exists():
        return None
    try:
        return json.loads(target_path.read_text(encoding='utf-8'))
    except Exception:
        return None


def deploy_model(
    session,
    model_version: str,
    actor: str,
    reason: str,
    model_dir: Path | str,
    target_environment: str = 'local'
) -> dict:
    """Configures a registered model for deployment. Requires restart for process activation."""
    if target_environment != 'local':
        raise ValueError('This installation supports only the local release environment')
    _release_lock(session)
    _publish_after_commit(session)
    if not actor or not actor.strip():
        raise ValueError("Actor must be provided")
    if not reason or len(reason.strip()) < 3:
        raise ValueError("Reason must be at least 3 characters")

    row = session.execute(
        text("SELECT * FROM models WHERE model_version = :v"),
        {'v': model_version}
    ).mappings().one_or_none()
    if row is None:
        raise ValueError(f"Model version '{model_version}' is not registered")

    if row['review_status'] in ('rejected', 'archived'):
        raise ValueError('Model review status forbids deployment')

    # Verify physical artifacts on disk
    verified = verify_model_bundle(model_dir, row['bundle_digest'])
    if verified['bundle_digest'] != row['bundle_digest']:
        raise ValueError("Candidate artifact digest does not match registered model digest")

    # Supersede previous desired deployment
    session.execute(
        text("UPDATE model_deployments SET status = 'superseded' WHERE target_environment = 'local' AND status = 'desired'")
    )

    deployment_id = uuid4()
    session.execute(
        text("""INSERT INTO model_deployments (
            id, model_id, model_version, target_environment, action, status, actor, reason
        ) VALUES (
            :id, :m_id, :ver, :env, 'deploy', 'desired', :actor, :reason
        )"""),
        {
            'id': deployment_id,
            'm_id': row['id'],
            'ver': model_version,
            'env': target_environment,
            'actor': actor.strip(),
            'reason': reason.strip()
        }
    )

    # Write atomic release pointer
    release_info = {
        'deployment_id': str(deployment_id),
        'desired_version': model_version,
        'model_dir': str(Path(model_dir).resolve()),
        'bundle_digest': row['bundle_digest'],
        'target_environment': target_environment,
        'actor': actor.strip(),
        'reason': reason.strip(),
        'configured_at': datetime.now(timezone.utc).isoformat()
    }
    session.info['release_pending'] = True

    # Record audit event
    session.execute(
        text("""INSERT INTO auth_audit_events (
            id, tenant_id, actor_id, action, target_type, target_id, request_id, details
        ) VALUES (
            gen_random_uuid(), NULL, NULL, 'model_deployed', 'model', :target_id, gen_random_uuid(),
            :details
        )"""),
        {
            'target_id': row['id'],
            'details': json.dumps({
                'deployment_id': str(deployment_id),
                'model_version': model_version,
                'action': 'deploy',
                'release_pointer': release_info,
                'actor': actor.strip(),
                'reason': reason.strip()
            })
        }
    )

    return release_info


def rollback_model(
    session,
    target_version: str,
    actor: str,
    reason: str,
    model_dir: Path | str,
    target_environment: str = 'local'
) -> dict:
    """Rolls back desired deployment to a previously verified registered model."""
    if target_environment != 'local':
        raise ValueError('This installation supports only the local release environment')
    _release_lock(session)
    _publish_after_commit(session)
    if not actor or not actor.strip():
        raise ValueError("Actor must be provided")
    if not reason or len(reason.strip()) < 3:
        raise ValueError("Reason must be at least 3 characters")

    target_model = session.execute(
        text("SELECT * FROM models WHERE model_version = :v"),
        {'v': target_version}
    ).mappings().one_or_none()
    if target_model is None:
        raise ValueError(f"Rollback target model '{target_version}' is not registered")

    # Verify that target_version was previously deployed
    prev_deploy = session.execute(
        text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND model_version = :v"),
        {'v': target_version}
    ).mappings().first()
    if prev_deploy is None:
        raise ValueError(f"Rollback target model '{target_version}' has never been deployed in history")

    # Check if target is already the desired deployment
    current_desired = session.execute(
        text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND status = 'desired' ORDER BY created_at DESC LIMIT 1")
    ).mappings().one_or_none()
    if current_desired and current_desired['model_version'] == target_version:
        raise ValueError(f"Rollback target '{target_version}' is already the desired deployment")

    if target_model['review_status'] in ('rejected', 'archived'):
        raise ValueError('Model review status forbids rollback')

    # Verify physical artifacts on disk for the rollback target
    verified = verify_model_bundle(model_dir, target_model['bundle_digest'])
    if verified['bundle_digest'] != target_model['bundle_digest']:
        raise ValueError("Rollback artifact digest does not match registered model digest")

    # Supersede previous desired deployment
    session.execute(
        text("UPDATE model_deployments SET status = 'superseded' WHERE target_environment = 'local' AND status = 'desired'")
    )

    deployment_id = uuid4()
    session.execute(
        text("""INSERT INTO model_deployments (
            id, model_id, model_version, target_environment, action, status, actor, reason
        ) VALUES (
            :id, :m_id, :ver, :env, 'rollback', 'desired', :actor, :reason
        )"""),
        {
            'id': deployment_id,
            'm_id': target_model['id'],
            'ver': target_version,
            'env': target_environment,
            'actor': actor.strip(),
            'reason': reason.strip()
        }
    )

    release_info = {
        'deployment_id': str(deployment_id),
        'desired_version': target_version,
        'model_dir': str(Path(model_dir).resolve()),
        'bundle_digest': target_model['bundle_digest'],
        'target_environment': target_environment,
        'action': 'rollback',
        'actor': actor.strip(),
        'reason': reason.strip(),
        'configured_at': datetime.now(timezone.utc).isoformat()
    }
    session.info['release_pending'] = True

    session.execute(
        text("""INSERT INTO auth_audit_events (
            id, tenant_id, actor_id, action, target_type, target_id, request_id, details
        ) VALUES (
            gen_random_uuid(), NULL, NULL, 'model_rollback', 'model', :target_id, gen_random_uuid(),
            :details
        )"""),
        {
            'target_id': target_model['id'],
            'details': json.dumps({
                'deployment_id': str(deployment_id),
                'model_version': target_version,
                'action': 'rollback',
                'release_pointer': release_info,
                'actor': actor.strip(),
                'reason': reason.strip()
            })
        }
    )

    return release_info


def _matches_model(session, deployment, predictor):
    model = session.execute(text('SELECT model_digest,report_digest,bundle_digest FROM models WHERE id=:id'),
                            {'id': deployment['model_id']}).mappings().one()
    return (deployment['model_version'] == predictor.meta.get('version')
            and model['model_digest'] == predictor.meta.get('model_sha256')
            and model['report_digest'] == predictor.meta.get('report_sha256')
            and model['bundle_digest'] == getattr(predictor, 'bundle_sha256', None))


def record_activation(session, running_predictor) -> dict | None:
    """Updates deployment state upon server boot to verify desired == active model."""
    if running_predictor is None:
        return None

    _release_lock(session)
    running_version = str(running_predictor.meta.get('version'))
    running_digest = str(running_predictor.meta.get('model_sha256'))

    desired = session.execute(
        text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND status = 'desired' ORDER BY created_at DESC LIMIT 1")
    ).mappings().one_or_none()

    if desired is None:
        # Check if an active record already exists for this version
        active = session.execute(
            text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND status = 'active' AND model_version = :v ORDER BY activated_at DESC LIMIT 1"),
            {'v': running_version}
        ).mappings().one_or_none()
        if active and _matches_model(session, active, running_predictor):
            return dict(active)
        return None

    if _matches_model(session, desired, running_predictor):
        # One active record for the local environment.
        session.execute(text("UPDATE model_deployments SET status='superseded' WHERE target_environment='local' AND status='active'"))
        # Successful activation
        session.execute(
            text("""UPDATE model_deployments
                    SET status = 'active', activated_at = clock_timestamp()
                    WHERE id = :id"""),
            {'id': desired['id']}
        )
        session.execute(
            text("""INSERT INTO auth_audit_events (
                id, tenant_id, actor_id, action, target_type, target_id, request_id, details
            ) VALUES (
                gen_random_uuid(), NULL, NULL, 'model_activated', 'model', :target_id, gen_random_uuid(),
                :details
            )"""),
            {
                'target_id': desired['model_id'],
                'details': json.dumps({
                    'deployment_id': str(desired['id']),
                    'model_version': running_version,
                    'model_digest': running_digest,
                    'status': 'active'
                })
            }
        )
        updated = session.execute(
            text("SELECT * FROM model_deployments WHERE id = :id"),
            {'id': desired['id']}
        ).mappings().one()
        return dict(updated)
    else:
        # Mismatch / failed activation
        session.execute(
            text("UPDATE model_deployments SET status = 'failed' WHERE id = :id"),
            {'id': desired['id']}
        )
        return None


def get_deployment_status(session, running_predictor=None) -> dict:
    """Inspects desired deployment versus active running process state."""
    desired = session.execute(
        text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND status = 'desired' ORDER BY created_at DESC LIMIT 1")
    ).mappings().one_or_none()

    active = session.execute(
        text("SELECT * FROM model_deployments WHERE target_environment = 'local' AND status = 'active' ORDER BY activated_at DESC NULLS LAST LIMIT 1")
    ).mappings().one_or_none()

    running_version = running_predictor.meta.get('version') if running_predictor else None

    state = 'unconfigured'
    if desired:
        state = 'pending_restart' if running_predictor else 'desired_not_running'
    elif running_predictor:
        state = 'active' if active and _matches_model(session, active, running_predictor) else 'active_untracked'
    elif active:
        state = 'recorded_active_unverified'

    return {
        'state': state,
        'running_model_version': running_version,
        'desired_deployment': dict(desired) if desired else None,
        'active_deployment': dict(active) if active else None,
        'release_pointer': read_release_file()
    }


def list_deployments(session, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = session.execute(
        text("SELECT * FROM model_deployments ORDER BY created_at DESC LIMIT :lim OFFSET :off"),
        {'lim': max(1, min(limit, 100)), 'off': max(0, offset)}
    ).mappings().all()
    return [dict(r) for r in rows]
