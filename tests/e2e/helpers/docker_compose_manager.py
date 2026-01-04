"""Docker Compose Manager for Dual Composition E2E Tests.

Manages lifecycle of two separate docker-compose environments:
- Media Service composition (MediaMTX + media-service)
- STS Service composition (real STS service with ASR + Translation + TTS)

Provides coordinated startup, health checks, and cleanup.
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


class DockerComposeManager:
    """Manages Docker Compose lifecycle for a single composition.

    Supports starting, stopping, health checks, and log retrieval
    for a docker-compose.yml file.

    Usage:
        manager = DockerComposeManager(
            compose_file=Path("apps/media-service/docker-compose.yml"),
            project_name="e2e-media"
        )
        manager.start()
        # ... run tests ...
        manager.stop()
    """

    def __init__(
        self,
        compose_file: Path,
        project_name: str,
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialize Docker Compose manager.

        Args:
            compose_file: Path to docker-compose.yml
            project_name: Docker Compose project name (for network/volume isolation)
            env: Optional environment variables to pass to docker-compose
        """
        self.compose_file = compose_file
        self.project_name = project_name
        self.env = env or {}
        self._started = False

    def _run_compose(
        self,
        *args: str,
        capture_output: bool = True,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """Run docker compose command.

        Args:
            *args: Command arguments
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise on non-zero exit
            env: Optional environment variables (merged with self.env)

        Returns:
            Completed process result
        """
        import os

        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "-p",
            self.project_name,
            *args,
        ]

        # Merge environment variables
        merged_env = dict(os.environ)
        merged_env.update(self.env)
        if env:
            merged_env.update(env)

        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=check,
                env=merged_env,
            )
            return result
        except subprocess.CalledProcessError as e:
            # Log the full error output for debugging
            logger.error(f"Docker compose command failed: {' '.join(cmd)}")
            if e.stdout:
                logger.error(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                logger.error(f"STDERR:\n{e.stderr}")
            raise

    def start(
        self,
        build: bool = True,
        timeout: int = 60,
        health_check_endpoints: list[tuple[str, str]] | None = None,
        services: list[str] | None = None,
    ) -> None:
        """Start Docker Compose services.

        Args:
            build: Whether to rebuild images
            timeout: Startup timeout in seconds
            health_check_endpoints: Optional list of (url, name) tuples for health checks
            services: Optional list of service names to start (default: all services)
        """
        if self._started:
            logger.warning(f"Docker composition {self.project_name} already started")
            return

        logger.info(f"Starting Docker composition: {self.project_name}...")

        # Build and start services
        args = ["up", "-d"]
        if build:
            args.append("--build")

        # Add specific services if provided
        if services:
            args.extend(services)

        self._run_compose(*args)

        # Wait for services to be healthy
        self._wait_for_healthy(timeout, health_check_endpoints)

        self._started = True
        logger.info(f"Docker composition {self.project_name} started successfully")

    def stop(self, volumes: bool = True) -> None:
        """Stop Docker Compose services.

        Args:
            volumes: Whether to remove volumes
        """
        logger.info(f"Stopping Docker composition: {self.project_name}...")

        args = ["down"]
        if volumes:
            args.extend(["-v", "--remove-orphans"])

        self._run_compose(*args, check=False)

        self._started = False
        logger.info(f"Docker composition {self.project_name} stopped")

    def get_status(self) -> list[ServiceStatus]:
        """Get status of all services.

        Returns:
            List of service statuses
        """
        result = self._run_compose("ps", "--format", "json", check=False)

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

    def wait_for_health(
        self,
        timeout: int = 30,
        health_check_endpoints: list[tuple[str, str]] | None = None,
    ) -> None:
        """Wait for services to become healthy.

        Args:
            timeout: Timeout in seconds
            health_check_endpoints: Optional list of (url, name) tuples for health checks

        Raises:
            TimeoutError: If services don't become healthy
        """
        self._wait_for_healthy(timeout, health_check_endpoints)

    def _wait_for_healthy(
        self,
        timeout: int,
        health_check_endpoints: list[tuple[str, str]] | None = None,
    ) -> None:
        """Wait for all services to be healthy.

        Args:
            timeout: Timeout in seconds
            health_check_endpoints: Optional list of (url, name) tuples for health checks

        Raises:
            TimeoutError: If services don't become healthy
        """
        start_time = time.time()

        logger.info(f"Waiting for {self.project_name} services to be healthy...")

        while time.time() - start_time < timeout:
            # Check container states
            services = self.get_status()

            if all(svc.is_healthy for svc in services):
                logger.info(
                    f"{self.project_name}: All containers report healthy, verifying endpoints..."
                )

                # Verify health endpoints if provided
                if health_check_endpoints:
                    if self._verify_health_endpoints(health_check_endpoints):
                        logger.info(f"{self.project_name}: All health endpoints responding")
                        return
                else:
                    # No health check endpoints, trust container health
                    return

            time.sleep(2)

        # Timeout - print logs for debugging
        logger.error(f"{self.project_name}: Services failed to become healthy")
        logs = self.get_logs(tail=50)
        logger.error(f"{self.project_name} container logs:\n{logs}")

        raise TimeoutError(
            f"{self.project_name}: Docker services failed to become healthy within {timeout} seconds"
        )

    def _verify_health_endpoints(self, endpoints: list[tuple[str, str]]) -> bool:
        """Verify health endpoints are responding.

        Args:
            endpoints: List of (url, name) tuples

        Returns:
            True if all endpoints are healthy
        """
        with httpx.Client(timeout=5.0) as client:
            for url, name in endpoints:
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    logger.debug(f"{self.project_name}: {name} health check passed")
                except (httpx.HTTPError, httpx.ConnectError) as e:
                    logger.debug(f"{self.project_name}: {name} health check failed: {e}")
                    return False

        return True

    def is_running(self) -> bool:
        """Check if services are running.

        Returns:
            True if services are started
        """
        return self._started


class DualComposeManager:
    """Manages two separate Docker Compose environments.

    Coordinates startup and teardown of:
    1. Media Service composition (MediaMTX + media-service)
    2. STS Service composition (real STS service)

    Services communicate via localhost + port exposure.

    Usage:
        manager = DualComposeManager(
            media_compose_file=Path("apps/media-service/docker-compose.e2e.yml"),
            sts_compose_file=Path("apps/sts-service/docker-compose.e2e.yml"),
        )
        manager.start_all()
        # ... run tests ...
        manager.stop_all()
    """

    def __init__(
        self,
        media_compose_file: Path,
        sts_compose_file: Path,
        media_project_name: str = "e2e-media",
        sts_project_name: str = "e2e-sts",
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialize dual compose manager.

        Args:
            media_compose_file: Path to media-service docker-compose.yml
            sts_compose_file: Path to sts-service docker-compose.yml
            media_project_name: Project name for media composition
            sts_project_name: Project name for STS composition
            env: Optional environment variables (applied to both compositions)
        """
        self.media_manager = DockerComposeManager(
            compose_file=media_compose_file,
            project_name=media_project_name,
            env=env,
        )
        self.sts_manager = DockerComposeManager(
            compose_file=sts_compose_file,
            project_name=sts_project_name,
            env=env,
        )

    def start_all(
        self,
        build: bool = True,
        timeout: int = 60,
        media_health_endpoints: list[tuple[str, str]] | None = None,
        sts_health_endpoints: list[tuple[str, str]] | None = None,
    ) -> None:
        """Start both Docker Compose environments.

        STS service is started first to ensure it's ready when media-service connects.

        Args:
            build: Whether to rebuild images
            timeout: Startup timeout per composition
            media_health_endpoints: Health check endpoints for media services
            sts_health_endpoints: Health check endpoints for STS service
        """
        logger.info("Starting dual Docker Compose environments...")

        # Start STS service first (media-service will connect to it)
        logger.info("Step 1/2: Starting STS composition...")
        self.sts_manager.start(
            build=build,
            timeout=timeout,
            health_check_endpoints=sts_health_endpoints,
        )

        # Start media service composition
        logger.info("Step 2/2: Starting media composition...")
        self.media_manager.start(
            build=build,
            timeout=timeout,
            health_check_endpoints=media_health_endpoints,
        )

        logger.info("Dual Docker Compose environments started successfully")

    def stop_all(self, volumes: bool = True) -> None:
        """Stop both Docker Compose environments.

        Args:
            volumes: Whether to remove volumes
        """
        logger.info("Stopping dual Docker Compose environments...")

        # Stop in reverse order (media first, then STS)
        self.media_manager.stop(volumes=volumes)
        self.sts_manager.stop(volumes=volumes)

        logger.info("Dual Docker Compose environments stopped")

    def get_all_logs(self, tail: int = 100) -> dict[str, str]:
        """Get logs from both compositions.

        Args:
            tail: Number of lines to retrieve per composition

        Returns:
            Dictionary with 'media' and 'sts' logs
        """
        return {
            "media": self.media_manager.get_logs(tail=tail),
            "sts": self.sts_manager.get_logs(tail=tail),
        }

    def is_running(self) -> bool:
        """Check if both compositions are running.

        Returns:
            True if both are started
        """
        return self.media_manager.is_running() and self.sts_manager.is_running()
