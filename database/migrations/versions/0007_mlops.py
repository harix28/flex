"""MLOps model registry, deployment tracking, monitoring runs, and inference latency."""
from alembic import op

revision = '0007_mlops'
down_revision = '0006_work_orders'
branch_labels = None
depends_on = None

AUTH_ACTIONS = "'login_success','login_failure','login_rate_limited','logout','password_changed','membership_added','membership_changed','membership_disabled','bootstrap','user_created','user_disabled'"
REGISTRY_ACTIONS = "'machine_created','machine_updated','machine_archived','sensor_created','sensor_updated','installation_created','installation_removed'"
PREDICTION_ACTIONS = "'prediction_requested','prediction_completed','prediction_failed'"
WORK_ORDER_ACTIONS = "'work_order_created','work_order_approved','work_order_assigned','work_order_transitioned','work_order_priority_changed','work_order_updated','work_order_note_added','work_order_cancelled','work_order_completed'"
MLOPS_ACTIONS = "'model_registered','model_deployed','model_activated','model_rollback','model_monitoring_run'"


def upgrade():
    # 1. Extend audit events to support MLOps lifecycle actions and optional details payload
    op.execute("ALTER TABLE auth_audit_events ADD COLUMN details jsonb")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check')
    op.execute(f"ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ({AUTH_ACTIONS},{REGISTRY_ACTIONS},{PREDICTION_ACTIONS},{WORK_ORDER_ACTIONS},{MLOPS_ACTIONS}))")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT audit_target_check')
    op.execute(f"""ALTER TABLE auth_audit_events ADD CONSTRAINT audit_target_check CHECK
      ((action NOT IN ({REGISTRY_ACTIONS},{PREDICTION_ACTIONS},{WORK_ORDER_ACTIONS},{MLOPS_ACTIONS}))
       OR (target_id IS NOT NULL AND target_type IS NOT NULL
           AND target_type IN ('machine','sensor','installation','prediction','work_order','model','monitoring_run')
           AND (action IN ({MLOPS_ACTIONS}) OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL))))""")

    # 2. Immutable model registry table
    op.execute("""CREATE TABLE models (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      model_version text NOT NULL UNIQUE CHECK (length(trim(model_version)) >= 3 AND length(model_version) <= 64),
      model_family text NOT NULL CHECK (model_family IN ('xgboost', 'ridge', 'constant', 'custom')),
      bundle_digest text NOT NULL CHECK (bundle_digest ~ '^[0-9a-f]{64}$'),
      model_digest text NOT NULL CHECK (model_digest ~ '^[0-9a-f]{64}$'),
      report_digest text NOT NULL CHECK (report_digest ~ '^[0-9a-f]{64}$'),
      feature_schema text NOT NULL CHECK (length(trim(feature_schema)) >= 3),
      feature_count integer NOT NULL CHECK (feature_count > 0),
      window_size integer NOT NULL CHECK (window_size >= 2),
      target_subset text NOT NULL CHECK (target_subset IN ('FD001', 'FD002', 'FD003', 'FD004')),
      target_machine_type text NOT NULL,
      target_data_source text NOT NULL,
      training_provenance jsonb NOT NULL,
      evaluation_metrics jsonb NOT NULL,
      registration_actor text NOT NULL CHECK (length(trim(registration_actor)) >= 1),
      review_status text NOT NULL DEFAULT 'experiment_only' CHECK (review_status IN ('experiment_only', 'reviewed_candidate', 'rejected', 'archived')),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")

    # 3. Model deployments / release tracking table
    op.execute("""CREATE TABLE model_deployments (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      model_id uuid NOT NULL REFERENCES models(id) ON DELETE RESTRICT,
      model_version text NOT NULL,
      target_environment text NOT NULL DEFAULT 'local' CHECK (target_environment IN ('local', 'staging', 'production')),
      action text NOT NULL CHECK (action IN ('deploy', 'rollback', 'deactivate')),
      status text NOT NULL CHECK (status IN ('desired', 'active', 'failed', 'superseded')),
      actor text NOT NULL CHECK (length(trim(actor)) >= 1),
      reason text NOT NULL CHECK (length(trim(reason)) >= 3),
      activated_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("CREATE INDEX idx_model_deployments_status ON model_deployments(status, created_at DESC)")

    # 4. ML monitoring runs table (input drift and ground-truth evaluation)
    op.execute("""CREATE TABLE ml_monitoring_runs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      model_version text NOT NULL,
      run_type text NOT NULL CHECK (run_type IN ('drift', 'evaluation')),
      status text NOT NULL CHECK (status IN ('available', 'insufficient_data', 'incompatible_reference', 'failed')),
      sample_count integer NOT NULL CHECK (sample_count >= 0),
      engine_count integer NOT NULL DEFAULT 0 CHECK (engine_count >= 0),
      metrics jsonb NOT NULL,
      actor text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("CREATE INDEX idx_ml_monitoring_runs_tenant ON ml_monitoring_runs(tenant_id, run_type, created_at DESC)")

    # 5. Add inference latency columns to predictions table
    op.execute("ALTER TABLE predictions ADD COLUMN inference_ms double precision CHECK (inference_ms IS NULL OR inference_ms >= 0)")
    op.execute("ALTER TABLE predictions ADD COLUMN pipeline_ms double precision CHECK (pipeline_ms IS NULL OR pipeline_ms >= 0)")


def downgrade():
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS pipeline_ms")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS inference_ms")
    op.execute("DROP TABLE IF EXISTS ml_monitoring_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS model_deployments CASCADE")
    op.execute("DROP TABLE IF EXISTS models CASCADE")
    op.execute("ALTER TABLE auth_audit_events DROP COLUMN IF EXISTS details")
