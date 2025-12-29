"""Entrypoint for running Echo STS Service standalone.

Usage:
    python -m sts_service.echo
    python -m sts_service.echo --port 8000
    python -m sts_service.echo --host 0.0.0.0 --port 8000
"""

import argparse
import logging
import os
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the echo service."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Echo STS Service - Protocol-compliant mock for E2E testing"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("ECHO_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("ECHO_PORT", "8000")),
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser.parse_args()


def main() -> None:
    """Main entrypoint for the echo service."""
    args = parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Echo STS Service on {args.host}:{args.port}")

    try:
        import uvicorn

        from sts_service.echo.server import create_app

        app = create_app()

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            reload=args.reload,
        )
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install 'sts-service[dev]'")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
