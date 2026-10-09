"""Isolated migrated database. Test providers never call live services."""

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="salesway-tests-"))
os.environ["DATABASE_URL"] = os.environ.get(
    "SALESWAY_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{TEST_ROOT}/tests.db"
)
os.environ["WORKER_MODE"] = "manual"
os.environ["AI_PROVIDER"] = "local"
os.environ["APIFY_API_TOKEN"] = "test-token"
os.environ["EMAIL_PROVIDER"] = "local"
os.environ["CALENDAR_PROVIDER"] = "local"
os.environ["LIVE_DELIVERY_ENABLED"] = "false"
os.environ["LOCAL_MAIL_DIR"] = str(TEST_ROOT / "mail")
os.environ["API_TOKEN"] = ""
os.environ["WEBHOOK_SECRET"] = "local-webhook-test-secret"

from app.core.config import settings
from app.main import create_app


@pytest.fixture(scope="session")
def test_app():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    return create_app()


@pytest.fixture(scope="session")
def client(test_app):
    with TestClient(test_app, raise_server_exceptions=True) as instance:
        yield instance


@pytest.fixture(autouse=True)
def fresh_database(client):
    async def reset():
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.db.base import Base
        from app.db.engine import get_engine
        from app.models.sales import WorkspaceSettings

        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as db:
            for table in reversed(Base.metadata.sorted_tables):
                await db.execute(delete(table))
            db.add(WorkspaceSettings(id=1))
            await db.commit()

    client.portal.call(reset)
    settings.API_TOKEN = ""
    settings.EMAIL_PROVIDER = "local"
    settings.CALENDAR_PROVIDER = "local"
    settings.AI_PROVIDER = "local"
    yield


@pytest.fixture
def drain(client):
    from app.tasks.worker import drain as process

    return lambda: client.portal.call(process)
