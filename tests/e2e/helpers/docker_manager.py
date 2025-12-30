"""Docker Compose lifecycle management for E2E tests.

Provides utilities to start, stop, and monitor Docker Compose services
for E2E testing with health checks and cleanup.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from tests.e2e.config import (
    DockerComposeConfig,
    EchoSTSConfig,
    MediaMTXConfig,
    MediaServiceConfig,
    TimeoutConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Status of a Docker Compose service."""

    name: str
    container_name: str
    state: str
    health: str | None
    ports: list[str]
    is_healthy: bool

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ServiceStatus:
        """Create ServiceStatus from docker compose ps JSON output."""
        health = data.get("Health", "")
        state = data.get("State", "")
        return cls(
            name=data.get("Service", ""),
            container_name=data.get("Name", ""),
            state=state,
            health=health,
            ports=data.get("Publishers", []),
            is_healthy=state == "running" and (health == "healthy" or health == ""),
        )


class DockerManager:
    """Manages Docker Compose lifecycle for E2E tests.

    Provides start, stop, and health check functionality for the
    E2E test environment (MediaMTX + echo-sts + media-service).

    Usage:
        manager = DockerManager()
        await manager.start()
        # ... run tests ...
        await manager.stop()
    """

    def __init__(
        self,
        compose_file: Path | None = None,
        project_name: str | None = None,
    ) -> None:
        """Initialize Docker manager.

        Args:
            compose_file: Path to docker-compose.yml (default: tests/e2e/docker-compose.yml)
            project_name: Docker Compose project name (default: e2e-tests)
        """
        self.compose_file = compose_file or DockerComposeConfig.COMPOSE_FILE
        self.project_name = project_name or DockerComposeConfig.PROJECT_NAME
        self._started = False

    def _run_compose(
        self,
        *args: str,
        capture_output: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run docker compose command.

        Args:
            *args: Command arguments
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise on non-zero exit

        Returns:
            Completed process result
        """
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "-p",
            self.project_name,
            *args,
        ]
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=capture_output, text=True, check=check)

    def start(self, build: bool = True, timeout: int | None = None) -> None:
        """Start Docker Compose services.

        Args:
            build: Whether to rebuild images
            timeout: Startup timeout in seconds (default: SERVICE_STARTUP_TIMEOUT)
        """
        if self._started:
            logger.warning("Docker services already started")
            return

        timeout = timeout or TimeoutConfig.SERVICE_STARTUP

        logger.info("Starting E2E Docker services...")

        # Build and start services
        args = ["up", "-d"]
        if build:
            args.append("--build")

        self._run_compose(*args)

        # Wait for services to be healthy
        self._wait_for_healthy(timeout)

        self._started = True
        logger.info("E2E Docker services started successfully")

    def stop(self, volumes: bool = True) -> None:
        """Stop Docker Compose services.

        Args:
            volumes: Whether to remove volumes
        """
        logger.info("Stopping E2E Docker services...")

        args = ["down"]
        if volumes:
            args.extend(["-v", "--remove-orphans"])

        self._run_compose(*args, check=False)

        self._started = False
        logger.info("E2E Docker services stopped")

    def get_status(self) -> list[ServiceStatus]:
        """Get status of all services.

        Returns:
            List of service statuses
        """
        result = self._run_compose("ps", "--format", "json")

        services = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    services.append(ServiceStatus.from_json(data))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse service status: {line}")

        return services

    def get_logs(self, service: str | None = None, tail: int = 100) -> str:
        """Get container logs.

        Args:
            service: Service name (default: all services)
            tail: Number of lines to retrieve

        Returns:
            Log output
        """
        args = ["logs", "--tail", str(tail)]
        if service:
            args.append(service)

        result = self._run_compose(*args, check=False)
        return result.stdout + result.stderr

    def _wait_for_healthy(self, timeout: int) -> None:
        """Wait for all services to be healthy.

        Args:
            timeout: Timeout in seconds

        Raises:
            TimeoutError: If services don't become healthy
        """
        start_time = time.time()

        logger.info("Waiting for services to be healthy...")

        while time.time() - start_time < timeout:
            # Check container states
            services = self.get_status()

            if all(svc.is_healthy for svc in services):
                logger.info("All containers report healthy, verifying endpoints...")

                # Verify health endpoints are responding
                if self._verify_health_endpoints():
                    logger.info("All health endpoints responding")
                    return

            time.sleep(2)

        # Timeout - print logs for debugging
        logger.error("Services failed to become healthy")
        logs = self.get_logs(tail=50)
        logger.error(f"Container logs:\n{logs}")

        raise TimeoutError(
            f"Docker services failed to become healthy within {timeout} seconds"
        )

    def _verify_health_endpoints(self) -> bool:
        """Verify health endpoints are responding.

        Returns:
            True if all endpoints are healthy
        """
        endpoints = [
            (MediaMTXConfig.CONTROL_API_URL + "/v3/paths/list", "MediaMTX"),
            (EchoSTSConfig.URL + "/socket.io/?transport=polling", "Echo STS"),
            (MediaServiceConfig.HEALTH_URL, "Media Service"),
        ]

        with httpx.Client(timeout=5.0) as client:
            for url, name in endpoints:
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    logger.debug(f"{name} health check passed")
                except (httpx.HTTPError, httpx.ConnectError) as e:
                    logger.debug(f"{name} health check failed: {e}")
                    return False

        return True

    def is_running(self) -> bool:
        """Check if services are running.

        Returns:
            True if services are started
        """
        return self._started

    def restart_service(self, service: str) -> None:
        """Restart a specific service.

        Args:
            service: Service name to restart
        """
        logger.info(f"Restarting service: {service}")
        self._run_compose("restart", service)
        time.sleep(2)  # Give service time to restart

    def stop_service(self, service: str) -> None:
        """Stop a specific service.

        Args:
            service: Service name to stop
        """
        logger.info(f"Stopping service: {service}")
        self._run_compose("stop", service)

    def start_service(self, service: str) -> None:
        """Start a specific service.

        Args:
            service: Service name to start
        """
        logger.info(f"Starting service: {service}")
        self._run_compose("start", service)
