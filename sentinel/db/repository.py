"""Internal registry access; HTTP callers supply context from verified session membership.
This UUID is a scope, NOT authentication. Never construct it from an HTTP body.
Raw SQL/database credentials are privileged; RLS is not implemented.
"""
from uuid import UUID, uuid4
from sqlalchemy import MetaData, Table, select

class RegistryRepository:
    def __init__(self, session, *, tenant_id):
        if not isinstance(tenant_id, UUID):
            raise ValueError('Explicit UUID tenant context required')
        self.session = session
        self.tenant_id = tenant_id
        self.metadata = MetaData()

    def _table(self, name):
        if name not in ('machines', 'sensors', 'installations', 'memberships'):
            raise ValueError('Unsupported registry table')
        return Table(name, self.metadata, autoload_with=self.session.connection())

    def get(self, table, record_id):
        t = self._table(table)
        return self.session.execute(select(t).where(t.c.tenant_id == self.tenant_id, t.c.id == record_id)).mappings().one_or_none()

    def list(self, table):
        t = self._table(table)
        return self.session.execute(select(t).where(t.c.tenant_id == self.tenant_id).order_by(t.c.id)).mappings().all()

    def add(self, table, **values):
        if 'tenant_id' in values:
            raise ValueError('Tenant ownership comes from repository context')
        t = self._table(table)
        values.setdefault('id', uuid4())
        self.session.execute(t.insert().values(tenant_id=self.tenant_id, **values))
        return values['id']

    def retire_machine(self, record_id):
        t = self._table('machines')
        return self.session.execute(t.update().where(t.c.tenant_id == self.tenant_id, t.c.id == record_id)
            .values(operating_status='retired', version=t.c.version + 1)).rowcount == 1
