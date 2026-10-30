"""PostgreSQL foundation. No HTTP registry or authentication surface."""
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sentinel.config import validate_database_url

REVISION = '0010_rls'

class Database:
    def __init__(self, url):
        self.engine = create_engine(validate_database_url(url), pool_size=5,
            max_overflow=0, pool_timeout=3, pool_pre_ping=True, hide_parameters=True,
            connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=5000 -c lock_timeout=3000 -c timezone=UTC'})

    @contextmanager
    def transaction(self):
        with Session(self.engine) as session, session.begin():
            yield session

    def ready(self):
        try:
            with self.engine.connect() as connection:
                return connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == REVISION
        except SQLAlchemyError:
            return False

    def close(self):
        self.engine.dispose()
