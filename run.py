"""Serve website"""

import waitress

from app.config import (
    logger,
    IP_ADDRESS,
    PORT_NUMBER
)

from app.src.web.routes import flask_api


logger.info("Starting application")
logger.info("Parsing secrets and variables")


if __name__ == "__main__":
    waitress.serve(
        flask_api,
        host=IP_ADDRESS,
        port=PORT_NUMBER,
        threads=8,
        channel_timeout=600,
    )
