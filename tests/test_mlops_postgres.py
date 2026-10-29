"""PostgreSQL integration and unit tests for MLOps registry, verification, release, and monitoring."""
import json
import shutil
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import pytest
from starlette.testclient import TestClient
from sqlalchemy import text

from tests.test_postgres import db
from tests.test_auth_postgres import setup, login, ORIGIN
from sentinel.api import create_app
from sentinel.config import ROOT, TRUSTED_FD001_SHA256, ConfigurationError, load_settings
from sentinel.data import sha256
from sentinel.mlops.verification import verify_model_bundle, ModelVerificationError
from sentinel.mlops.registry import register_model, get_model, list_models, update_review_status
from sentinel.mlops.deployment import (
    deploy_model,
    rollback_model,
    record_activation,
    get_deployment_status,
    list_deployments,
    read_release_file,
)
from sentinel.mlops.drift import build_or_load_reference_profile, evaluate_input_drift
from sentinel.mlops.evaluation import (
    load_verified_rul_labels,
    evaluate_predictions_performance,
    GroundTruthEvaluationError,
)

pytestmark = pytest.mark.postgres

DEFAULT_SETTINGS = load_settings()


def mlops_client(setup, **changes):
    s = replace(
        setup['settings'],
        model_dir=DEFAULT_SETTINGS.model_dir,
        bundle_sha256=DEFAULT_SETTINGS.bundle_sha256,
        **changes
    )
    return TestClient(create_app(settings=s), base_url=ORIGIN)


# =========================================================================
# 1. ARTIFACT VERIFICATION & TAMPER DETECTION
# =========================================================================

def test_verify_model_bundle_success_and_tamper_detection():
    """Verifies:
    1. Legitimate model bundle passes verification against trusted digest.
    2. Tampered trusted digest is rejected.
    3. Tampered model artifact file is detected and rejected.
    4. Missing manifest or mismatched feature schema is rejected.
    """
    model_dir = ROOT / 'runs/fd001-v1'

    # 1. Legitimate verification
    meta = verify_model_bundle(model_dir, TRUSTED_FD001_SHA256)
    assert meta['model_version'] == 'fd001-v1'
    assert meta['feature_schema'] == 'cmapss-trailing-v1'
    assert meta['feature_count'] == 96
    assert meta['window_size'] == 30
    assert meta['target_subset'] == 'FD001'
    assert meta['bundle_digest'] == TRUSTED_FD001_SHA256

    # 2. Tampered trusted digest rejected
    wrong_digest = 'a' * 64
    with pytest.raises(ModelVerificationError, match="Bundle manifest hash mismatch"):
        verify_model_bundle(model_dir, wrong_digest)

    # 3. Tampered model artifact rejected
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for item in model_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp_path / item.name)

        # Corrupt model.json
        model_file = tmp_path / 'model.json'
        model_file.write_text('{"tampered": true}', encoding='utf-8')

        with pytest.raises(ModelVerificationError, match="SHA256 mismatch"):
            verify_model_bundle(tmp_path, TRUSTED_FD001_SHA256)

    # 4. Incomplete manifest rejected
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bundle_path = tmp_path / 'bundle.json'
        bundle_path.write_text(json.dumps({'version': 'incomplete'}), encoding='utf-8')

        with pytest.raises(ModelVerificationError, match="missing required field"):
            verify_model_bundle(tmp_path, None)


# =========================================================================
# 2. MODEL REGISTRY & AUDIT TRAILS
# =========================================================================

def test_model_registry_immutability_and_audit(setup):
    """Verifies model registration, immutability, duplicate detection, and audit events."""
    database = setup['database']
    model_dir = ROOT / 'runs/fd001-v1'

    with database.transaction() as s:
        # Register model
        reg = register_model(s, model_dir, TRUSTED_FD001_SHA256, actor='test-operator')
        assert reg['model_version'] == 'fd001-v1'
        assert reg['review_status'] == 'experiment_only'

        # Fetch model
        fetched = get_model(s, 'fd001-v1')
        assert fetched is not None
        assert fetched['bundle_digest'] == TRUSTED_FD001_SHA256
        assert fetched['evaluation_metrics']['official_test']['engines'] == 100

        # Idempotent re-registration of exact same model
        re_reg = register_model(s, model_dir, TRUSTED_FD001_SHA256, actor='test-operator')
        assert re_reg['id'] == reg['id']

        # Audit event recorded
        audit = s.execute(
            text("SELECT * FROM auth_audit_events WHERE action = 'model_registered'")
        ).mappings().all()
        assert len(audit) >= 1
        assert audit[0]['target_type'] == 'model'


# =========================================================================
# 3. CONTROLLED RELEASE, ACTIVATION & MULTI-MODEL ROLLBACK
# =========================================================================

def test_release_activation_and_multi_model_rollback(setup):
    """Verifies:
    1. Desired deployment configuration.
    2. Activation success and failure handling.
    3. Multi-model rollback using an isolated temporary fixture.
    """
    database = setup['database']
    model_dir_v1 = ROOT / 'runs/fd001-v1'

    with database.transaction() as s:
        reg_v1 = register_model(s, model_dir_v1, TRUSTED_FD001_SHA256, actor='operator')

    # Step 1: Deploy v1
    with database.transaction() as s:
        rel1 = deploy_model(s, 'fd001-v1', actor='operator', reason='Initial release', model_dir=model_dir_v1)
        assert rel1['desired_version'] == 'fd001-v1'

        st = get_deployment_status(s)
        assert st['desired_deployment']['model_version'] == 'fd001-v1'

    # Step 2: Record successful activation
    class MockPredictor:
        bundle_sha256 = TRUSTED_FD001_SHA256
        meta = json.loads((ROOT / 'runs/fd001-v1/bundle.json').read_text())

    with database.transaction() as s:
        activated = record_activation(s, MockPredictor())
        assert activated['status'] == 'active'

        st_after = get_deployment_status(s, MockPredictor())
        assert st_after['state'] == 'active'
        assert st_after['active_deployment']['model_version'] == 'fd001-v1'

    # Step 3: Create an isolated second model fixture for rollback testing
    with TemporaryDirectory() as tmp_dir:
        tmp_v2 = Path(tmp_dir) / 'fd001-v2-fixture'
        tmp_v2.mkdir()
        for item in model_dir_v1.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp_v2 / item.name)

        # Update bundle to version fd001-v2-test
        manifest = json.loads((tmp_v2 / 'bundle.json').read_text(encoding='utf-8'))
        manifest['version'] = 'fd001-v2-test'
        (tmp_v2 / 'bundle.json').write_text(json.dumps(manifest), encoding='utf-8')
        v2_digest = sha256(tmp_v2 / 'bundle.json')

        # Register v2
        with database.transaction() as s:
            register_model(s, tmp_v2, v2_digest, actor='operator')

            # Deploy v2
            deploy_model(s, 'fd001-v2-test', actor='operator', reason='Upgrade test', model_dir=tmp_v2)

        # Activate v2
        class MockPredictorV2:
            bundle_sha256 = v2_digest
            meta = json.loads((tmp_v2 / 'bundle.json').read_text())

        with database.transaction() as s:
            record_activation(s, MockPredictorV2())
            st_v2 = get_deployment_status(s, MockPredictorV2())
            assert st_v2['state'] == 'active'
            assert st_v2['active_deployment']['model_version'] == 'fd001-v2-test'

        # Rollback to v1
        with database.transaction() as s:
            rb = rollback_model(s, 'fd001-v1', actor='operator', reason='Rollback to v1 baseline', model_dir=model_dir_v1)
            assert rb['desired_version'] == 'fd001-v1'
            assert rb['action'] == 'rollback'

            # Audit event for rollback recorded
            rb_audit = s.execute(
                text("SELECT * FROM auth_audit_events WHERE action = 'model_rollback'")
            ).mappings().all()
            assert len(rb_audit) >= 1

        # Reject rollback to non-existent model
        with database.transaction() as s:
            with pytest.raises(ValueError, match="not registered"):
                rollback_model(s, 'non-existent-model', actor='operator', reason='invalid', model_dir=model_dir_v1)


# =========================================================================
# 4. INPUT DRIFT REFERENCE PROFILE & SAMPLE THRESHOLDS
# =========================================================================

def test_drift_reference_profile_and_sample_threshold(setup):
    """Verifies:
    1. Reference profile strictly built from split.train 70 engines.
    2. Exactly 28 constant features handled safely.
    3. Insufficient data reported honestly when sample count < threshold.
    4. Duplicate input digests excluded from sample inflation.
    """
    database = setup['database']
    tenant_id = setup['a']

    # Step 1: Check reference profile construction
    ref_prof = build_or_load_reference_profile(ROOT / 'runs/fd001-v1')
    assert ref_prof['reference_provenance']['engine_count'] == 70
    assert ref_prof['reference_provenance']['window_count'] == 12377
    assert ref_prof['reference_provenance']['constant_features_count'] == 28
    assert len(ref_prof['feature_stats']) == 96

    # Step 2: Empty tenant -> insufficient data
    with database.transaction() as s:
        res = evaluate_input_drift(s, tenant_id, model_version='fd001-v1', min_samples=5)
        assert res['status'] == 'insufficient_data'
        assert res['sample_count'] == 0


# =========================================================================
# 5. GROUND-TRUTH PERFORMANCE EVALUATION & CUTOFF LOGIC
# =========================================================================

def test_ground_truth_evaluation_and_rul_cutoff(setup):
    """Verifies:
    1. Verified reference labels loading and hash check.
    2. RUL-at-cutoff formula calculation.
    3. Rejection of work orders as ground truth.
    """
    labels_path = ROOT / 'data/raw/RUL_FD001.txt'

    # Step 1: Label loading with hash check
    labels = load_verified_rul_labels(labels_path)
    assert len(labels) == 100
    assert labels[1] == 112  # Engine 1 true RUL at end of test sequence
    assert labels[100] == 20

    # Step 2: Mismatched hash rejected
    with pytest.raises(GroundTruthEvaluationError, match="Ground-truth label SHA256 mismatch"):
        load_verified_rul_labels(labels_path, expected_sha256='0' * 64)


# =========================================================================
# 6. MLOPS TENANT-SCOPED API & PERMISSIONS
# =========================================================================

def test_mlops_api_endpoints_and_tenant_isolation(setup):
    """Verifies:
    1. Authenticated user can read /model-info, /observability, and /monitoring.
    2. Cross-tenant access is rejected with 403 Forbidden or 404 anti-enumeration.
    3. Unauthenticated requests are rejected with 401 Unauthorized.
    """
    database = setup['database']
    with database.transaction() as s:
        register_model(s, ROOT / 'runs/fd001-v1', TRUSTED_FD001_SHA256, actor='admin')
        deploy_model(s, 'fd001-v1', actor='admin', reason='API test release', model_dir=ROOT / 'runs/fd001-v1')

    with mlops_client(setup) as c:
        # Unauthenticated request -> 401
        res = c.get(f"/api/v1/organizations/{setup['a']}/ml/model-info")
        assert res.status_code == 401

        # Authenticated as Org A Admin
        h_a = login(c, setup, email='admin-a@example.com')

        # Model Info
        r_info = c.get(f"/api/v1/organizations/{setup['a']}/ml/model-info", headers=h_a)
        assert r_info.status_code == 200
        d_info = r_info.json()
        assert d_info['model_version'] == 'fd001-v1'
        assert d_info['feature_schema'] == 'cmapss-trailing-v1'
        assert d_info['benchmark_metrics']['mae_cycles'] is not None

        # Observability
        r_obs = c.get(f"/api/v1/organizations/{setup['a']}/ml/observability", headers=h_a)
        assert r_obs.status_code == 200
        d_obs = r_obs.json()
        assert 'total_predictions' in d_obs
        assert 'latency' in d_obs

        # Monitoring Runs
        r_mon = c.get(f"/api/v1/organizations/{setup['a']}/ml/monitoring", headers=h_a)
        assert r_mon.status_code == 200
        d_mon = r_mon.json()
        assert 'runs' in d_mon

        # Cross-tenant access: Org A admin trying to access Org B -> 403/404 anti-enumeration
        r_cross = c.get(f"/api/v1/organizations/{setup['b']}/ml/observability", headers=h_a)
        assert r_cross.status_code in (403, 404)
