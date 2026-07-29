import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
from dotenv import load_dotenv

# Load nearest .env walking up (repo-root locally); app .env overrides.
# Docker image is /app/... so parents[3] does not exist — never index blindly.
_HERE = Path(__file__).resolve()
_APP_ROOT = _HERE.parents[1]
for _parent in _HERE.parents:
    _candidate = _parent / ".env"
    if _candidate.is_file():
        load_dotenv(_candidate, override=False)
        break
load_dotenv(_APP_ROOT / ".env", override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./presales_hub.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Enable WAL mode for SQLite (better concurrent reads)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import opportunity, proposal, stakeholder, approval, user  # noqa: F401
    Base.metadata.create_all(bind=engine)
