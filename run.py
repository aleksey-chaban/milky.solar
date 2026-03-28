"""Serve website"""

import multiprocessing
from gunicorn.app.base import BaseApplication

from app.config import (
    logger,
    IP_ADDRESS,
    PORT_NUMBER
)

from app.src.web.routes import flask_api


logger.info("Starting application")
logger.info("Parsing secrets and variables")


class InitializeApplication(BaseApplication):
    """Load Flask app into Gunicorn"""

    def __init__(self, app, options=None):
        self.application = app
        self.options = options or {}
        super().__init__()

    def load_config(self):
        """Load Gunicorn configuration"""

        cfg = {k: v for k, v in self.options.items()
               if k in self.cfg.settings and v is not None}
        for k, v in cfg.items():
            self.cfg.set(k, v)

    def load(self):
        """Load Flask application"""

        return self.application


if __name__ == "__main__":
    workers = 2 * multiprocessing.cpu_count() + 1
    options = {
        "bind": f"{IP_ADDRESS}:{PORT_NUMBER}",
        "workers": workers,
        "worker_class": "sync",
        "timeout": 180,
        "keepalive": 5,
        "max_requests": 1000,
        "max_requests_jitter": 200,
    }

    InitializeApplication(flask_api, options).run()
