"""
Alembic environment configuration for PRESALES HUB.

Database URL resolution order:
  1. DATABASE_URL environment variable  (CI, staging, production)
  2. sqlalchemy.url in alembic.ini       (local dev default)

SQLite / PostgreSQL compatibility:
  - render_as_batch=True  enables copy-alter for SQLite (ALTER TABLE workaround)
  - NullPool prevents connection pooling during migrations (safe for both dialects)
  - compare_type=True detects column type changes in autogenerate

Adding a new model:
  Import it in the "Register models" section below.  If omitted, autogenerate
  will not see the table and will emit a DROP TABLE on the next run.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Path ──────────────────────────────────────────────────────────────────────
# Resolve hub-api as the package root so `from db.database import Base` works
# when alembic is run from hub-api/ or from any parent directory.
_here = os.path.dirname(os.path.abspath(__file__))
_api_root = os.path.dirname(_here)
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Register models ───────────────────────────────────────────────────────────
# Every model module must be imported here so its tables register with
# Base.metadata before autogenerate or upgrade runs.
# When you add a new models/foo.py, add: import models.foo  # noqa: F401
from db.database import Base   # noqa: E402
import models.stakeholder      # noqa: F401, E402
import models.opportunity      # noqa: F401, E402
import models.proposal         # noqa: F401, E402
import models.approval         # noqa: F401, E402

target_metadata = Base.metadata


# ── URL resolution ────────────────────────────────────────────────────────────
def get_url() -> str:
    """Return DATABASE_URL env var if set, otherwise fall back to alembic.ini."""
    return os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")


def _is_sqlite(url: str) -> bool:
    return url.lower().startswith("sqlite")


# ── Offline mode — generate SQL script without a live connection ──────────────
def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode — run against a live DB connection ────────────────────────────
def run_migrations_online() -> None:
    url = get_url()

    # Inject the resolved URL into the config section so engine_from_config picks it up.
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = url

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # Never pool in migrations — always a dedicated connection
    )

    # Set SQLite PRAGMA via engine-level event so it fires at the DBAPI layer
    # before SQLAlchemy opens any transaction.  Running PRAGMA inside the
    # connection block would trigger SQLAlchemy 2.x autobegin, which
    # wraps the whole migration in an implicit transaction that gets rolled
    # back on context-manager exit — causing alembic_version to be empty.
    if _is_sqlite(url):
        from sqlalchemy import event as sa_event  # noqa: E402

        @sa_event.listens_for(connectable, "connect")
        def _sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(url),   # SQLite ALTER TABLE via copy-alter
            compare_type=True,                  # Detect column type changes
            compare_server_default=True,        # Detect server default drift
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
