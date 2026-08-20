"""
API tests for health endpoints.

These tests verify that:
  - All three health endpoints return HTTP 200.
  - Response bodies contain the expected fields and values.
  - Response time headers are present.
"""

from typing import Any

import pytest


class TestHealthBasic:
    """GET /health"""

    def test_returns_200(self, client) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_response_shape(self, client) -> None:
        data: dict[str, Any] = client.get("/health").json()
        assert data["status"] == "alive"
        assert "app" in data
        assert "version" in data
        assert "env" in data
        assert "timestamp" in data

    def test_request_id_header_present(self, client) -> None:
        response = client.get("/health")
        assert "x-request-id" in response.headers

    def test_process_time_header_present(self, client) -> None:
        response = client.get("/health")
        assert "x-process-time" in response.headers


class TestHealthLive:
    """GET /health/live"""

    def test_returns_200(self, client) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_status_alive(self, client) -> None:
        data = client.get("/health/live").json()
        assert data["status"] == "alive"


class TestHealthReady:
    """GET /health/ready"""

    def test_returns_200(self, client) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200

    def test_response_shape(self, client) -> None:
        data: dict[str, Any] = client.get("/health/ready").json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data

    def test_checks_keys_present(self, client) -> None:
        checks = client.get("/health/ready").json()["checks"]
        assert "database" in checks
        assert "redis" in checks

    def test_overall_status_valid(self, client) -> None:
        status = client.get("/health/ready").json()["status"]
        assert status in ("ready", "degraded")
