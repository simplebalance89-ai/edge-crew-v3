"""
Edge Crew v3.0 — Root entry point for local dev.
In production (Docker), app/main.py is used instead.
This just re-exports the app for `uvicorn main:app`.
"""

from app.main import app  # noqa: F401
