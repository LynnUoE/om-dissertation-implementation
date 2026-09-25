"""
WSGI entry point for production servers, e.g.:

    gunicorn --chdir backend --threads 8 -b 0.0.0.0:5001 wsgi:app

Validates the configuration and loads the reranker model at startup, like
running api_server.py directly, and refuses to start if that fails.
"""
from api_server import app, initialize_app

if not initialize_app():
    raise SystemExit("LitFinder failed to initialize; see the log above")
