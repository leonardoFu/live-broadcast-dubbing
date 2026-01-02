"""Test /metrics endpoint exposure."""
import pytest
from fastapi.testclient import TestClient
from media_service.main import app


def test_metrics_endpoint_exists():
    """Test /metrics endpoint returns 200 OK."""
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_endpoint_exposes_prometheus_format():
    """Test /metrics returns valid Prometheus text format."""
    client = TestClient(app)
    response = client.get("/metrics")

    # Should contain Prometheus format markers
    assert "# HELP" in response.text
    assert "# TYPE" in response.text
