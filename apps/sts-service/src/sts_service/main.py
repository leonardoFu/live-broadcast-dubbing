"""Main entrypoint for integrated STS Service.

This module provides the ASGI application for the full STS service
integrating Whisper ASR, Translation, and Coqui TTS.

Usage with uvicorn:
    uvicorn sts_service.main:sio_app --host 0.0.0.0 --port 3000
"""

import logging
import os

# For now, use echo service as a placeholder
# TODO: Implement full STS service integration with ASR + Translation + TTS
from sts_service.echo.server import create_app

logger = logging.getLogger(__name__)

# Create ASGI app
sio_app = create_app()

logger.info("STS Service initialized (using echo implementation for now)")
