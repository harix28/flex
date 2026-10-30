"""Durable tenant-scoped background jobs."""
from alembic import op

revision = '0008_outbox'
down_revision = '0007_mlops'
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE outbox_events (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL REFERENCES tenants(id),
        event_type text NOT NULL CHECK (event_type = 'drift.evaluate'),
        source_event_id text NOT NULL CHECK (length(btrim(source_event_id)) BETWEEN 1 AND 128),
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','claimed','delivered','dead_letter')),
        attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 10),
        lease_token uuid, lease_until timestamptz,
        next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        error_code text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        completed_at timestamptz,
        UNIQUE (tenant_id, event_type, source_event_id),
        CHECK ((status = 'claimed') = (lease_token IS NOT NULL AND lease_until IS NOT NULL))
    )""")
    op.execute("CREATE INDEX outbox_claim ON outbox_events(next_attempt_at, created_at) WHERE status IN ('pending','claimed')")
    op.execute("CREATE VIEW outbox_dead_letter AS SELECT * FROM outbox_events WHERE status = 'dead_letter'")


def downgrade():
    op.execute('DROP VIEW outbox_dead_letter')
    op.execute('DROP TABLE outbox_events')
