from alembic import context
from sentinel.config import load_database_url
from sentinel.db import Database

if context.is_offline_mode():
    context.configure(url='postgresql+psycopg://', literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(context.config.attributes.get('database_url') or load_database_url())
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.close()
