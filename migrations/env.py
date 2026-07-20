from logging.config import fileConfig

from alembic import context

from app.config import Settings
from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import normalize_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    settings = Settings(_env_file=None)
    return normalize_database_url(settings.database_url)


def run_migrations_offline() -> None:
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    url = get_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    connectable = create_engine(url, connect_args=connect_args, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
