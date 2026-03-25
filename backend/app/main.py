"""
Ponto de entrada ASGI — carrega ambiente e expõe `app` para uvicorn (app.main:app).
A API HTTP vive em presentation.api.
"""

from pathlib import Path

from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env", override=True)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from app.presentation.api.app import create_app

app = create_app()
