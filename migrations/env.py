import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

# Build DB URL directly — bypasses ConfigParser so special chars in password are safe
def _db_url():
    user = os.environ.get("DATABASE_USER", "orderuser")
    password = os.environ.get("DATABASE_PASSWORD", "changeme")
    host = os.environ.get("DATABASE_HOST", "localhost")
    port = os.environ.get("DATABASE_PORT", "5432")
    name = os.environ.get("DATABASE_NAME", "orderdb")
    from sqlalchemy.engine import URL
    return URL.create("postgresql+psycopg2", username=user, password=password,
                      host=host, port=int(port), database=name,
                      query={"sslmode": os.environ.get("DATABASE_SSLMODE", "prefer")})


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_db_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
