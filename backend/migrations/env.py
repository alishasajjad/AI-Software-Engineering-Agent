from __future__ import annotations

import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models as models_package
from app.core.config import settings
from app.db.base import Base


def import_all_model_modules() -> None:
    """
    Import every module inside app.models.

    SQLAlchemy models register themselves with Base.metadata
    when their modules are imported. Alembic autogenerate
    therefore needs all model modules loaded before comparing
    metadata with the database.
    """

    package_prefix = (
        f"{models_package.__name__}."
    )

    for module_info in pkgutil.iter_modules(
        models_package.__path__,
        package_prefix,
    ):
        importlib.import_module(
            module_info.name
        )


# Register all SQLAlchemy models with Base.metadata.
import_all_model_modules()


config = context.config

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )


config.set_main_option(
    "sqlalchemy.url",
    settings.database_url,
)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.
    """

    config_section = config.get_section(
        config.config_ini_section,
        {},
    )

    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()