import asyncio
from logging.config import fileConfig
import os
import sys

# Add the project root to the Python path so Alembic can find your 'services' folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Import your Base (so Alembic can read your tables)
from services.gateway.db_models import Base
# 2. Import your dynamic URI builder
from services.gateway.database import _get_db_uri

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. CRITICAL: Set the metadata so --autogenerate actually works!
target_metadata = Base.metadata

# 4. Inject your async PostgreSQL URL into Alembic's config
db_url = _get_db_uri(
    os.getenv("DB_USER", "root"),
    os.getenv("DB_PASSWORD", "password"),
    os.getenv("DB_HOST", "localhost"),
    int(os.getenv("DB_PORT", 5432)),
    os.getenv("DB_NAME", "eventforge")
)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an async Engine
    and associate a connection with the context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()