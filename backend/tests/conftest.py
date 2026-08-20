"""
Pytest fixtures shared across all tests.

The session-scoped TestClient means the FastAPI app is only
created once per test session, which is fast and sufficient for
unit / API tests that do not require a live database.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="session")
def test_app():
    """Session-scoped FastAPI application instance."""
    return create_app()


@pytest.fixture(scope="session")
def client(test_app):
    """Session-scoped synchronous TestClient."""
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c
