"""PostgreSQL Row-Level Security (RLS) policies for strict database-level tenant isolation."""
from alembic import op

revision = '0010_rls'
down_revision = '0009_fleet_jobs'
branch_labels = None
depends_on = None

TABLES = [
    'machines',
    'replay_streams',
    'replay_observations',
    'predictions',
    'work_orders',
    'outbox_events'
]


def upgrade():
    for tbl in TABLES:
        # Enable RLS
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        # Define tenant isolation policy using session setting 'app.current_tenant_id'
        # Allows explicit 'bypass' for admin/migration tasks, or matches tenant_id UUID
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {tbl}
            FOR ALL
            USING (
                current_setting('app.current_tenant_id', true) = 'bypass'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.current_tenant_id', true) = 'bypass'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
        """)


def downgrade():
    for tbl in TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")

