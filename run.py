"""Serve website"""

import waitress

from app.config import (
    IP_ADDRESS,
    PORT_NUMBER
)

from app.src.web.routes import flask_api


if __name__ == "__main__":
    waitress.serve(
        flask_api,
        host=IP_ADDRESS,
        port=PORT_NUMBER,
        threads=16,
        channel_timeout=600,
    )
