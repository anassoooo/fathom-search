"""ASGI entry point: `uvicorn vio.api.main:app`."""

from vio.api.app import create_app

app = create_app(configure_logs=True)
