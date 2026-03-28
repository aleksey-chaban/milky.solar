"""Serve website"""

import logging
import os
import sys

from logging.handlers import RotatingFileHandler
from venv import logger

import flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import redis


IP_ADDRESS = "0.0.0.0"
PORT_NUMBER = 10000

REDIS_URL = os.getenv("upstash_milky_solar_redis")

OPENAI_KEY = os.getenv("openai_milky_solar_key")
OPENAI_ORG = os.getenv("openai_milky_solar_org")
OPENAI_PROJECT = os.getenv("openai_milky_solar_project")

OPENAI_MODEL = os.getenv("openai_milky_solar_model")
POSTGRES_DB = os.getenv("postgres_milky_solar_db")
POSTGRES_USER = os.getenv("postgres_milky_solar_user")
POSTGRES_PASSWORD = os.getenv("postgres_milky_solar_pass")
POSTGRES_HOST = os.getenv("postgres_milky_solar_host")
POSTGRES_PORT = os.getenv("postgres_milky_solar_port")


def init_logger():
    """Create logger instance"""

    log_path = os.path.join(os.getcwd(), "logs", "site.log")

    if not os.path.exists(os.path.join(os.getcwd(), "logs")):
        os.mkdir(os.path.join(os.getcwd(), "logs"))

    if not os.path.exists(log_path):
        open(log_path, mode="w", encoding="utf8").close()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10240,
        backupCount=10
    )

    logging_config = {
        "level": logging.INFO,
        "format": "%(asctime)s | %(levelname)s | %(message)s",
    }

    logging.basicConfig(**logging_config)

    instance = logging.getLogger("logger")
    instance.propagate = False

    if not any(isinstance(h, RotatingFileHandler) for h in instance.handlers):
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10240,
            backupCount=10,
            encoding="utf8"
        )

        file_handler.setFormatter(logging.Formatter(logging_config["format"]))
        instance.addHandler(file_handler)

    if not any(
        isinstance(h, logging.StreamHandler)
        and getattr(h, "stream", None)
        is sys.stdout for h in instance.handlers
    ):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(logging.Formatter(logging_config["format"]))
        instance.addHandler(stdout_handler)

    return instance


logger = init_logger()

static_path = os.path.join(os.getcwd(), "app", "static")
template_path = os.path.join(os.getcwd(), "app", "templates")

flask_api = flask.Flask(
    __name__,
    static_folder=static_path,
    template_folder=template_path
)

try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    logger.info("Redis is reachable.")
except redis.exceptions.ConnectionError as e:
    logger.error("Redis is not reachable: %s", e)
    raise RuntimeError("Failed to connect to Redis") from e

limiter = Limiter(
    get_remote_address,
    app=flask_api,
    storage_uri=REDIS_URL,
    default_limits=[
        "100 per day",
        "30 per hour",
        "2 per minute"
    ]
)
