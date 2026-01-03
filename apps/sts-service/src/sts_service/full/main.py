"""Main entry point for Full STS Service.

Provides FastAPI + Socket.IO app for uvicorn.
"""

from .server import create_app

app = create_app()
