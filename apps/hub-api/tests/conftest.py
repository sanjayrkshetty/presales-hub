"""
Shared fixtures for PRESALES HUB regression tests.

Uses an in-memory SQLite database isolated per test via drop/create cycle.
FastAPI's get_db dependency is overridden so all router calls use the test engine.
The SLA worker background thread is suppressed — tests exercise _check_slas directly.
"""
import pytest
from fastapi.testclient import TestClient

from tests._testdb import TEST_ENGINE, TestSessionLocal


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Suppress SLA worker before importing main so no background thread starts ---
import workers.sla_worker as _sla_mod  # noqa: E402
_sla_mod.start = lambda: None

# --- Import app and wire dependency override ---
from db.database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def force_mock_llm_provider():
    """Force mock LLM provider for all tests — avoids real API calls."""
    import copilot_engine.config as cfg
    orig = cfg.LLM_PROVIDER
    cfg.LLM_PROVIDER = "mock"
    yield
    cfg.LLM_PROVIDER = orig



@pytest.fixture(autouse=True)
def force_hash_embeddings(monkeypatch):
    """CI/tests: avoid downloading sentence-transformers / torch."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    import memory_engine.config as mem_cfg
    monkeypatch.setattr(mem_cfg, "EMBEDDING_PROVIDER", "hash", raising=False)
    from memory_engine.embeddings.factory import get_embedding_provider
    get_embedding_provider.cache_clear()
    yield
    get_embedding_provider.cache_clear()

@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before each test for full isolation."""
    import models.opportunity   # noqa: F401
    import models.proposal      # noqa: F401
    import models.stakeholder   # noqa: F401
    import models.approval      # noqa: F401
    import models.intelligence  # noqa: F401 — intelligence tables
    import models.memory        # noqa: F401 — memory_chunks table
    import strategic_intelligence.models.strategy_models  # noqa: F401 — strategy tables
    import models.integration  # noqa: F401 — integration fabric tables
    import models.tenant       # noqa: F401 — platform tenant tables
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield


@pytest.fixture
def db():
    """Direct DB session for seeding test data."""
    session = TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    """Synchronous TestClient — does not trigger lifespan (no SLA worker thread)."""
    return TestClient(app)
