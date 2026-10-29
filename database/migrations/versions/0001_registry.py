"""Initial reviewed registry foundation; immutable SQL beside this revision."""
from pathlib import Path
from alembic import op
revision = '0001_registry'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    for statement in Path(__file__).with_suffix('.sql').read_text().split(';'):
        if statement.strip():
            op.execute(statement)

def downgrade():
    # Destructive: loses ALL foundation data. No CASCADE; dependencies block drops.
    for table in ('installations','sensors','machines','memberships','users','tenants'):
        op.drop_table(table)
    # Shared btree_gist extension deliberately retained.
