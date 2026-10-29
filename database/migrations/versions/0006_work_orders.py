"""Maintenance work orders, approval workflow, assignment and audit tracking."""
from alembic import op

revision = '0006_work_orders'
down_revision = '0005_predictions'
branch_labels = None
depends_on = None

AUTH_ACTIONS = "'login_success','login_failure','login_rate_limited','logout','password_changed','membership_added','membership_changed','membership_disabled','bootstrap','user_created','user_disabled'"
REGISTRY_ACTIONS = "'machine_created','machine_updated','machine_archived','sensor_created','sensor_updated','installation_created','installation_removed'"
PREDICTION_ACTIONS = "'prediction_requested','prediction_completed','prediction_failed'"
WORK_ORDER_ACTIONS = "'work_order_created','work_order_approved','work_order_assigned','work_order_transitioned','work_order_priority_changed','work_order_updated','work_order_note_added','work_order_cancelled','work_order_completed'"


def upgrade():
    # 1. Extend audit events to support work order actions and target type
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check')
    op.execute(f"ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ({AUTH_ACTIONS},{REGISTRY_ACTIONS},{PREDICTION_ACTIONS},{WORK_ORDER_ACTIONS}))")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT audit_target_check')
    op.execute(f"""ALTER TABLE auth_audit_events ADD CONSTRAINT audit_target_check CHECK
      ((action NOT IN ({REGISTRY_ACTIONS},{PREDICTION_ACTIONS},{WORK_ORDER_ACTIONS}))
       OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL AND target_id IS NOT NULL AND target_type IS NOT NULL
           AND target_type IN ('machine','sensor','installation','prediction','work_order')))""")

    # 2. Sequence counters table for organization-scoped work order numbers (e.g. WO-00001)
    op.execute("""CREATE TABLE work_order_counters (
      tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
      last_number integer NOT NULL DEFAULT 0 CHECK (last_number >= 0)
    )""")

    # 3. Work orders core table
    op.execute("""CREATE TABLE work_orders (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL,
      work_order_number text NOT NULL,
      machine_id uuid NOT NULL,
      title text NOT NULL CHECK (length(trim(title)) >= 3 AND length(title) <= 200),
      description text NOT NULL CHECK (length(trim(description)) >= 1 AND length(description) <= 4000),
      status text NOT NULL CHECK (status IN ('draft','approved','in_progress','blocked','completed','cancelled')),
      priority text NOT NULL CHECK (priority IN ('urgent','high','medium','low','unknown')),
      assigned_technician_id uuid,
      planned_date date,
      due_date date,
      created_by_id uuid NOT NULL,
      version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      
      -- State completion & cancellation & blocked details
      completion_summary text,
      completed_at timestamptz,
      cancellation_reason text,
      cancelled_at timestamptz,
      block_reason text,
      blocked_at timestamptz,

      -- Evidence snapshot for prediction-linked drafts
      origin text NOT NULL CHECK (origin IN ('prediction','manual')),
      prediction_id uuid,
      model_version text,
      model_digest text CHECK (model_digest IS NULL OR model_digest ~ '^[0-9a-f]{64}$'),
      bundle_digest text CHECK (bundle_digest IS NULL OR bundle_digest ~ '^[0-9a-f]{64}$'),
      stream_id uuid,
      cutoff_cycle integer CHECK (cutoff_cycle IS NULL OR cutoff_cycle > 0),
      rul_cycles double precision CHECK (rul_cycles IS NULL OR rul_cycles >= 0),
      prediction_status text CHECK (prediction_status IS NULL OR prediction_status IN ('available','unavailable')),
      release_status text CHECK (release_status IS NULL OR release_status = 'experiment_only'),
      policy_version text,
      snapshot_priority_band text CHECK (snapshot_priority_band IS NULL OR snapshot_priority_band IN ('urgent','high','medium','low','unknown')),

      -- Foreign keys guaranteeing tenant isolation
      FOREIGN KEY (tenant_id, machine_id) REFERENCES machines(tenant_id, id),
      FOREIGN KEY (tenant_id, created_by_id) REFERENCES memberships(tenant_id, user_id),
      FOREIGN KEY (tenant_id, assigned_technician_id) REFERENCES memberships(tenant_id, user_id),
      FOREIGN KEY (prediction_id) REFERENCES predictions(id),
      UNIQUE (tenant_id, work_order_number),

      -- State-specific constraints
      CHECK (status <> 'completed' OR (completion_summary IS NOT NULL AND length(trim(completion_summary)) >= 3 AND completed_at IS NOT NULL)),
      CHECK (status <> 'cancelled' OR (cancellation_reason IS NOT NULL AND length(trim(cancellation_reason)) >= 3 AND cancelled_at IS NOT NULL)),
      CHECK (status <> 'blocked' OR (block_reason IS NOT NULL AND length(trim(block_reason)) >= 3 AND blocked_at IS NOT NULL)),
      CHECK (status <> 'in_progress' OR assigned_technician_id IS NOT NULL),

      -- Origin-specific constraints
      CHECK (origin <> 'prediction' OR (
        prediction_id IS NOT NULL AND
        model_version IS NOT NULL AND
        model_digest IS NOT NULL AND
        bundle_digest IS NOT NULL AND
        cutoff_cycle IS NOT NULL AND
        rul_cycles IS NOT NULL AND
        prediction_status = 'available' AND
        release_status = 'experiment_only' AND
        policy_version IS NOT NULL AND
        snapshot_priority_band IS NOT NULL
      )),
      CHECK (origin <> 'manual' OR (
        prediction_id IS NULL AND
        model_version IS NULL AND
        model_digest IS NULL AND
        bundle_digest IS NULL AND
        cutoff_cycle IS NULL AND
        rul_cycles IS NULL AND
        prediction_status IS NULL AND
        release_status IS NULL AND
        policy_version IS NULL AND
        snapshot_priority_band IS NULL
      ))
    )""")

    # 4. Partial unique index: Only ONE active prediction-generated work order per machine
    op.execute("""CREATE UNIQUE INDEX work_orders_active_prediction_machine ON work_orders (tenant_id, machine_id)
      WHERE origin = 'prediction' AND status IN ('draft','approved','in_progress','blocked')""")

    # Query indexes
    op.execute('CREATE INDEX work_orders_tenant_status ON work_orders (tenant_id, status, created_at DESC)')
    op.execute('CREATE INDEX work_orders_machine ON work_orders (tenant_id, machine_id, created_at DESC)')
    op.execute('CREATE INDEX work_orders_technician ON work_orders (tenant_id, assigned_technician_id, status)')
    op.execute('CREATE INDEX work_orders_priority ON work_orders (tenant_id, priority, created_at DESC)')

    # 5. Transition history table (immutable)
    op.execute("""CREATE TABLE work_order_transitions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL,
      work_order_id uuid NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
      from_status text NOT NULL CHECK (from_status IN ('draft','approved','in_progress','blocked','completed','cancelled')),
      to_status text NOT NULL CHECK (to_status IN ('draft','approved','in_progress','blocked','completed','cancelled')),
      actor_id uuid NOT NULL,
      reason text,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY (tenant_id, actor_id) REFERENCES memberships(tenant_id, user_id)
    )""")
    op.execute('CREATE INDEX work_order_transitions_wo ON work_order_transitions (work_order_id, created_at ASC)')

    # 6. Assignment history table (immutable)
    op.execute("""CREATE TABLE work_order_assignments (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL,
      work_order_id uuid NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
      previous_assignee_id uuid,
      new_assignee_id uuid NOT NULL,
      assigned_by_id uuid NOT NULL,
      reason text,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY (tenant_id, new_assignee_id) REFERENCES memberships(tenant_id, user_id),
      FOREIGN KEY (tenant_id, assigned_by_id) REFERENCES memberships(tenant_id, user_id)
    )""")
    op.execute('CREATE INDEX work_order_assignments_wo ON work_order_assignments (work_order_id, created_at ASC)')

    # 7. Append-only work order notes table
    op.execute("""CREATE TABLE work_order_notes (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL,
      work_order_id uuid NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
      author_id uuid NOT NULL,
      note_text text NOT NULL CHECK (length(trim(note_text)) >= 1 AND length(note_text) <= 2000),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY (tenant_id, author_id) REFERENCES memberships(tenant_id, user_id)
    )""")
    op.execute('CREATE INDEX work_order_notes_wo ON work_order_notes (work_order_id, created_at ASC)')

    # 8. Idempotency tracking table
    op.execute("""CREATE TABLE work_order_idempotency (
      tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      idempotency_key text NOT NULL CHECK (length(trim(idempotency_key)) > 0 AND length(idempotency_key) <= 128),
      request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
      work_order_id uuid NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY (tenant_id, idempotency_key)
    )""")

    # 9. Immutability trigger on evidence snapshot and immutable history tables
    op.execute("""CREATE OR REPLACE FUNCTION work_orders_immutable_guard() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Work orders cannot be deleted';
      END IF;
      IF OLD.origin IS DISTINCT FROM NEW.origin
         OR OLD.prediction_id IS DISTINCT FROM NEW.prediction_id
         OR OLD.model_version IS DISTINCT FROM NEW.model_version
         OR OLD.model_digest IS DISTINCT FROM NEW.model_digest
         OR OLD.bundle_digest IS DISTINCT FROM NEW.bundle_digest
         OR OLD.stream_id IS DISTINCT FROM NEW.stream_id
         OR OLD.cutoff_cycle IS DISTINCT FROM NEW.cutoff_cycle
         OR OLD.rul_cycles IS DISTINCT FROM NEW.rul_cycles
         OR OLD.prediction_status IS DISTINCT FROM NEW.prediction_status
         OR OLD.release_status IS DISTINCT FROM NEW.release_status
         OR OLD.policy_version IS DISTINCT FROM NEW.policy_version
         OR OLD.snapshot_priority_band IS DISTINCT FROM NEW.snapshot_priority_band
         OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
         OR OLD.machine_id IS DISTINCT FROM NEW.machine_id
         OR OLD.work_order_number IS DISTINCT FROM NEW.work_order_number
         OR OLD.created_by_id IS DISTINCT FROM NEW.created_by_id
         OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'Work order evidence snapshot, identity, and creation provenance are immutable';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;""")

    op.execute("""CREATE TRIGGER work_orders_guard BEFORE UPDATE OR DELETE ON work_orders
      FOR EACH ROW EXECUTE FUNCTION work_orders_immutable_guard()""")

    # Protect history and notes from modification or deletion
    op.execute("""CREATE TRIGGER work_order_transitions_immutable BEFORE UPDATE OR DELETE ON work_order_transitions
      FOR EACH ROW EXECUTE FUNCTION replay_immutable()""")
    op.execute("""CREATE TRIGGER work_order_assignments_immutable BEFORE UPDATE OR DELETE ON work_order_assignments
      FOR EACH ROW EXECUTE FUNCTION replay_immutable()""")
    op.execute("""CREATE TRIGGER work_order_notes_immutable BEFORE UPDATE OR DELETE ON work_order_notes
      FOR EACH ROW EXECUTE FUNCTION replay_immutable()""")


def downgrade():
    op.execute(f"""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM work_orders) OR EXISTS(SELECT 1 FROM auth_audit_events WHERE action IN ({WORK_ORDER_ACTIONS})) THEN
        RAISE EXCEPTION 'Work order records exist; destructive downgrade refused';
      END IF;
    END $$""")
    op.execute('DROP TRIGGER IF EXISTS work_order_notes_immutable ON work_order_notes')
    op.execute('DROP TRIGGER IF EXISTS work_order_assignments_immutable ON work_order_assignments')
    op.execute('DROP TRIGGER IF EXISTS work_order_transitions_immutable ON work_order_transitions')
    op.execute('DROP TRIGGER IF EXISTS work_orders_guard ON work_orders')
    op.execute('DROP FUNCTION IF EXISTS work_orders_immutable_guard()')
    op.drop_table('work_order_idempotency')
    op.drop_table('work_order_notes')
    op.drop_table('work_order_assignments')
    op.drop_table('work_order_transitions')
    op.drop_table('work_orders')
    op.drop_table('work_order_counters')
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT audit_target_check')
    op.execute(f"""ALTER TABLE auth_audit_events ADD CONSTRAINT audit_target_check CHECK
      ((action NOT IN ({REGISTRY_ACTIONS},{PREDICTION_ACTIONS}))
       OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL AND target_id IS NOT NULL AND target_type IS NOT NULL
           AND target_type IN ('machine','sensor','installation','prediction')))""")
    op.execute('ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check')
    op.execute(f"ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ({AUTH_ACTIONS},{REGISTRY_ACTIONS},{PREDICTION_ACTIONS}))")
