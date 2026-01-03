"""Main entry point for Full STS Service.

Starts the FastAPI + Socket.IO server with uvicorn.
"""

import logging
import os

import uvicorn

from sts_service.full.server import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for Full STS Service."""
    # Get port from environment or use default
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Full STS Service on {host}:{port}")

    # Create app
    app = create_app()

    # Run with uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )

    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
