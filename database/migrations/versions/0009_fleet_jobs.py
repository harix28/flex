"""Fleet scoring jobs and persisted job results."""
from alembic import op

revision = '0009_fleet_jobs'
down_revision = '0008_outbox'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE outbox_events DROP CONSTRAINT outbox_events_event_type_check')
    op.execute("ALTER TABLE outbox_events ADD CONSTRAINT outbox_events_event_type_check CHECK (event_type IN ('drift.evaluate','fleet.score'))")
    op.execute("ALTER TABLE outbox_events ADD COLUMN result jsonb CHECK (result IS NULL OR jsonb_typeof(result)='object')")


def downgrade():
    # Refuse to silently discard queued work or its audit context.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM outbox_events WHERE event_type='fleet.score')
        THEN RAISE EXCEPTION 'Archive fleet jobs and remove them explicitly before downgrade'; END IF; END $$""")
    op.execute('ALTER TABLE outbox_events DROP COLUMN result')
    op.execute('ALTER TABLE outbox_events DROP CONSTRAINT outbox_events_event_type_check')
    op.execute("ALTER TABLE outbox_events ADD CONSTRAINT outbox_events_event_type_check CHECK (event_type='drift.evaluate')")
