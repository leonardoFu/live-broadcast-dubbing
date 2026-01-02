"""Dual Compose E2E Test: Service Communication (User Story 2).

Tests service discovery and connectivity via port exposure:
- MediaMTX health check
- Media-service health check
- STS-service health check
- Socket.IO connection establishment

Priority: P1 (MVP)
"""

import logging

import httpx
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.requires_docker
@pytest.mark.requires_sts
@pytest.mark.asyncio
async def test_services_can_communicate(dual_compose_env):
    """Test all services can communicate via localhost ports.

    Test Scenario:
    1. Query MediaMTX health endpoint
    2. Query media-service health endpoint
    3. Query sts-service health endpoint
    4. Verify all return 200 OK within 30 seconds

    Expected Results:
    - MediaMTX: GET http://localhost:8889/v3/paths/list → 200 OK
    - Media Service: GET http://localhost:8080/health → 200 OK
    - STS Service: GET http://localhost:3000/health → 200 OK

    This test MUST initially FAIL if:
    - Docker compose environments not started
    - Ports not exposed correctly
    - Health check endpoints not implemented
    """
    logger.info("Testing service communication via health endpoints...")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # Test 1: MediaMTX health
        logger.info("Step 1: Testing MediaMTX health...")
        resp = await client.get("http://localhost:8889/v3/paths/list")
        assert resp.status_code == 200, \
            f"MediaMTX health check should return 200, got {resp.status_code}"
        logger.info("MediaMTX health check: PASS")

        # Test 2: Media Service health
        logger.info("Step 2: Testing media-service health...")
        resp = await client.get("http://localhost:8080/health")
        assert resp.status_code == 200, \
            f"Media service health check should return 200, got {resp.status_code}"
        logger.info("Media service health check: PASS")

        # Test 3: STS Service health
        logger.info("Step 3: Testing sts-service health...")
        resp = await client.get("http://localhost:3000/health")
        assert resp.status_code == 200, \
            f"STS service health check should return 200, got {resp.status_code}"
        logger.info("STS service health check: PASS")

    logger.info("All service health checks PASSED")


@pytest.mark.e2e
@pytest.mark.requires_docker
@pytest.mark.requires_sts
@pytest.mark.asyncio
async def test_socketio_connection_established(sts_monitor):
    """Test Socket.IO connection to STS service.

    Test Scenario:
    1. Create Socket.IO client
    2. Connect to http://localhost:3000
    3. Verify handshake completes successfully
    4. Disconnect client

    Expected Results:
    - Connection succeeds
    - Client is in connected state

    This test MUST initially FAIL if:
    - STS service not running
    - Port 3000 not exposed
    - Socket.IO endpoint not available
    """
    logger.info("Testing Socket.IO connection to STS service...")

    # sts_monitor fixture already connects, verify it's connected
    assert sts_monitor.client.connected, \
        "Socket.IO client should be connected to STS service"

    logger.info("Socket.IO connection: PASS")

    # Test sending a ping event
    await sts_monitor.emit("ping", {"message": "test"})
    logger.info("Socket.IO emit: PASS")

    logger.info("Socket.IO connection test PASSED")
