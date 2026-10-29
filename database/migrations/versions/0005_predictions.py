"""Persistent RUL predictions, input window provenance and maintenance priority tracking."""
from alembic import op

revision = '0005_predictions'
down_revision = '0004_replay'
branch_labels = None
depends_on = None

AUTH_ACTIONS = "'login_success','login_failure','login_rate_limited','logout','password_changed','membership_added','membership_changed','membership_disabled','bootstrap','user_created','user_disabled'"
REGISTRY_ACTIONS = "'machine_created','machine_updated','machine_archived','sensor_created','sensor_updated','installation_created','installation_removed'"
PREDICTION_ACTIONS = "'prediction_requested','prediction_completed','prediction_failed'"


def upgrade():
    # Extend audit events to support prediction lifecycle
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check')
    op.execute(f"ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ({AUTH_ACTIONS},{REGISTRY_ACTIONS},{PREDICTION_ACTIONS}))")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT registry_audit_target')
    op.execute(f"""ALTER TABLE auth_audit_events ADD CONSTRAINT audit_target_check CHECK
      ((action NOT IN ({REGISTRY_ACTIONS},{PREDICTION_ACTIONS}))
       OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL AND target_id IS NOT NULL AND target_type IS NOT NULL
           AND target_type IN ('machine','sensor','installation','prediction')))""")

    # Create predictions table
    op.execute("""CREATE TABLE predictions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL,
      machine_id uuid NOT NULL,
      stream_id uuid,
      actor_id uuid NOT NULL,
      request_id uuid NOT NULL,
      status text NOT NULL CHECK (status IN ('available','unavailable')),
      reason text CHECK (reason IS NULL OR reason IN ('no_observations','insufficient_history','gaps_in_history','unsupported_machine','unsupported_subset','unsupported_model','nonfinite_model_output','invalid_stored_input')),
      requested_cutoff_cycle integer NOT NULL CHECK (requested_cutoff_cycle > 0),
      observed_cutoff_cycle integer CHECK (observed_cutoff_cycle IS NULL OR observed_cutoff_cycle > 0),
      input_start_cycle integer CHECK (input_start_cycle IS NULL OR input_start_cycle > 0),
      input_end_cycle integer CHECK (input_end_cycle IS NULL OR input_end_cycle > 0),
      input_observation_count integer NOT NULL CHECK (input_observation_count >= 0),
      input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
      model_version text NOT NULL,
      model_digest text NOT NULL CHECK (model_digest ~ '^[0-9a-f]{64}$'),
      bundle_digest text NOT NULL CHECK (bundle_digest ~ '^[0-9a-f]{64}$'),
      inference_version integer NOT NULL DEFAULT 1 CHECK (inference_version > 0),
      feature_schema_version integer NOT NULL DEFAULT 1 CHECK (feature_schema_version > 0),
      rul_cycles double precision CHECK (rul_cycles IS NULL OR (status = 'available' AND rul_cycles >= 0)),
      failure_probability double precision CHECK (failure_probability IS NULL),
      interval_lower double precision CHECK (interval_lower IS NULL),
      interval_upper double precision CHECK (interval_upper IS NULL),
      diagnosis_basis text NOT NULL DEFAULT 'unavailable' CHECK (diagnosis_basis = 'unavailable'),
      release_status text NOT NULL DEFAULT 'experiment_only' CHECK (release_status = 'experiment_only'),
      policy_version text NOT NULL DEFAULT 'v1-experimental',
      priority_band text CHECK (priority_band IS NULL OR priority_band IN ('urgent','high','medium','low','unknown')),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CHECK (status <> 'available' OR (rul_cycles IS NOT NULL AND reason IS NULL AND priority_band IS NOT NULL AND priority_band <> 'unknown')),
      CHECK (status <> 'unavailable' OR (rul_cycles IS NULL AND reason IS NOT NULL)),
      FOREIGN KEY (tenant_id, machine_id) REFERENCES machines(tenant_id, id),
      FOREIGN KEY (tenant_id, actor_id) REFERENCES memberships(tenant_id, user_id)
    )""")

    # Foreign key to replay_streams when stream_id is present
    op.execute("""ALTER TABLE predictions ADD CONSTRAINT predictions_stream_fkey
      FOREIGN KEY (tenant_id, machine_id, stream_id) REFERENCES replay_streams(tenant_id, machine_id, id)""")

    # Unique index for deduplication and idempotency:
    # source + cutoff + input digest + model digest + inference version
    op.execute("""CREATE UNIQUE INDEX predictions_dedup ON predictions
      (tenant_id, machine_id, stream_id, requested_cutoff_cycle, input_digest, model_digest, inference_version)
      NULLS NOT DISTINCT""")

    # Query indexes
    op.execute('CREATE INDEX predictions_machine_cutoff ON predictions (tenant_id, machine_id, requested_cutoff_cycle DESC, created_at DESC)')
    op.execute('CREATE INDEX predictions_tenant_created ON predictions (tenant_id, created_at DESC)')
    op.execute('CREATE INDEX predictions_priority ON predictions (tenant_id, priority_band, rul_cycles)')

    # Immutability trigger
    op.execute('CREATE TRIGGER predictions_immutable BEFORE UPDATE OR DELETE ON predictions FOR EACH ROW EXECUTE FUNCTION replay_immutable()')


def downgrade():
    op.execute(f"""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM predictions) OR EXISTS(SELECT 1 FROM auth_audit_events WHERE action IN ({PREDICTION_ACTIONS})) THEN
        RAISE EXCEPTION 'Prediction records exist; destructive downgrade refused';
      END IF;
    END $$""")
    op.execute('DROP TRIGGER predictions_immutable ON predictions')
    op.drop_table('predictions')
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT audit_target_check')
    op.execute(f"""ALTER TABLE auth_audit_events ADD CONSTRAINT registry_audit_target CHECK
      ((action NOT IN ({REGISTRY_ACTIONS}))
       OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL AND target_id IS NOT NULL AND target_type IS NOT NULL AND target_type IN ('machine','sensor','installation')))""")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check')
    op.execute(f"ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ({AUTH_ACTIONS},{REGISTRY_ACTIONS}))")
