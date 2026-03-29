"""Serve website"""

import logging
import os
import sys

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
    print("Redis is reachable.")
except redis.exceptions.ConnectionError as e:
    print(f"Redis is not reachable: {e}")
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
