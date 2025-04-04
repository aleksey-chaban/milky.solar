"""Serve website"""

import logging
import os
import random

from logging.handlers import RotatingFileHandler

import psycopg
from psycopg.rows import dict_row

import flask
from flask import Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import redis

import waitress

from openai import OpenAI

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

logger = logging.getLogger("waitress")
file_handler.setFormatter(logging.Formatter(logging_config["format"]))
logger.addHandler(file_handler)

static_path = os.path.join(os.getcwd(), "app", "static")
template_path = os.path.join(os.getcwd(), "app", "templates")

flask_api = flask.Flask(
    __name__,
    static_folder=static_path,
    template_folder=template_path
)

REDIS_URL = os.getenv("upstash_milky_solar_redis")

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

OPENAI_MODEL = "gpt-4o-2024-11-20"

OPENAI_KEY = os.getenv("openai_milky_solar_key")
OPENAI_ORG = os.getenv("openai_milky_solar_org")
OPENAI_PROJECT = os.getenv("openai_milky_solar_project")

POSTGRES_DB = os.getenv("postgres_milky_solar_db")
POSTGRES_USER = os.getenv("postgres_milky_solar_user")
POSTGRES_PASSWORD = os.getenv("postgres_milky_solar_pass")
POSTGRES_HOST = os.getenv("postgres_milky_solar_host")
POSTGRES_PORT = os.getenv("postgres_milky_solar_port")

def get_db_connection():
    """Create a new database connection."""
    return psycopg.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        row_factory=dict_row
    )

def fetch_prompt(prompt_id):
    """Retrieve a prompt from the database."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT instructions FROM prompts WHERE id = %s", (prompt_id,))
            return cursor.fetchone()["instructions"]

def get_story(scenario):
    """Retrieve a story from the specified scenario."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {scenario}")
            total_rows = cursor.fetchone()["count"]
            random_id = random.randint(1, total_rows)

            logger.info("%s index selected: %s", scenario, random_id)

            cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (random_id,))
            story = cursor.fetchone()["story"]

            logger.info("Retrieved story")

            return flask.jsonify({"story": story})

def unlock_story(request, database):
    """Unlock a story."""

    try:
        client = OpenAI(
            api_key=OPENAI_KEY,
            organization=OPENAI_ORG,
            project=OPENAI_PROJECT
        )
    except Exception as e:
        logger.error("Server error: %s", e)
        raise e

    system_instructions = fetch_prompt(1)

    logger.info("Gathered instructions")

    def generate():
        response_stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": system_instructions
                },
                {
                    "role": "user",
                    "content": request
                }
            ],
            stream=True
        )

        story_content = ""
        for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                text_chunk = chunk.choices[0].delta.content
                story_content += text_chunk
                yield text_chunk

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"INSERT INTO {database} (story) VALUES (%s) RETURNING id", (story_content,))
                story_id = cursor.fetchone()["id"]

                cursor.execute("INSERT INTO stories (scenario, story_id) VALUES (%s, %s)", (database, story_id))

                connection.commit()

            logger.info("Stored %s scenario %s", database, story_id)

        logger.info("Retrieved story")


    return Response(generate(), content_type="text/plain")

def unlock_guest(request):
    """Unlock a guest story."""

    try:
        client = OpenAI(
            api_key=OPENAI_KEY,
            organization=OPENAI_ORG,
            project=OPENAI_PROJECT
        )
    except Exception as e:
        logger.error("Server error: %s", e)
        raise e

    system_instructions = fetch_prompt(2)

    if not system_instructions:
        system_instructions = "Our guest is lost in the ether."

    logger.info("Gathered instructions")

    def generate(system_instructions=system_instructions):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": system_instructions
                },
                {
                    "role": "user",
                    "content": request
                }
            ],
            stream=False
        )

        guest_profile = response.choices[0].message.content

        logger.info("Gathered profile")

        system_instructions = fetch_prompt(3)

        logger.info("Gathered instructions")

        response_stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": system_instructions
                },
                {
                    "role": "user",
                    "content": guest_profile
                }
            ],
            stream=True
        )

        story_content = ""
        for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                text_chunk = chunk.choices[0].delta.content
                story_content += text_chunk
                yield text_chunk

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO guest (story) VALUES (%s) RETURNING id", (story_content,))
                story_id = cursor.fetchone()["id"]

                connection.commit()

            logger.info("Stored guest scenario %s", story_id)

        logger.info("Retrieved story")


    return Response(generate(system_instructions=system_instructions), content_type="text/plain")

def unlock_guest_scenario(request, scenario):
    """Unlock a guest scenario."""

    try:
        client = OpenAI(
            api_key=OPENAI_KEY,
            organization=OPENAI_ORG,
            project=OPENAI_PROJECT
        )
    except Exception as e:
        logger.error("Server error: %s", e)
        raise e

    system_instructions = fetch_prompt(2)

    if not system_instructions:
        system_instructions = "Our guest is lost in the ether."
        return system_instructions

    logger.info("Gathered instructions")

    def generate(system_instructions=system_instructions):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": system_instructions
                },
                {
                    "role": "user",
                    "content": request
                }
            ],
            stream=False
        )

        guest_profile = response.choices[0].message.content

        logger.info("Gathered profile")

        start_system_instructions = fetch_prompt(4)

        logger.info("Gathered instructions")

        end_system_instructions = fetch_prompt(5)

        logger.info("Gathered instructions")

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {scenario}")
                total_rows = cursor.fetchone()["count"]
                random_id = random.randint(1, total_rows)

                logger.info("%s index selected: %s", scenario, random_id)

                cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (random_id,))
                story = cursor.fetchone()["story"]

        logger.info("Retrieved story")

        system_instructions = "\n".join([start_system_instructions, story, end_system_instructions])

        response_stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.6,
            messages=[
                {
                    "role": "system",
                    "content": system_instructions
                },
                {
                    "role": "user",
                    "content": guest_profile
                }
            ],
            stream=True
        )

        story_content = ""
        for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                text_chunk = chunk.choices[0].delta.content
                story_content += text_chunk
                yield text_chunk

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO guest (story) VALUES (%s) RETURNING id", (story_content,))
                story_id = cursor.fetchone()["id"]

                connection.commit()

            logger.info("Stored guest scenario %s", story_id)

        logger.info("Retrieved story")


    return Response(generate(system_instructions=system_instructions), content_type="text/plain")

@limiter.exempt
@flask_api.route("/")
def home():
    """Render the home page."""
    return flask.render_template("index.html")

scenarios = [
    "israel",
    "australia",
    "newzealand",
    "otherworld",
    "california",
    "unitedkingdom"
]

user_scenarios = [
    "guest",
    "israel",
    "australia",
    "newzealand",
    "otherworld",
    "california",
    "unitedkingdom",
    "random"
]

for scenario in scenarios:
    lambda_function = lambda s=scenario: get_story(s)
    lambda_function = limiter.exempt(lambda_function)
    flask_api.add_url_rule(f"/{scenario}", f"get_{scenario}_story", lambda_function, methods=["GET"])

@limiter.exempt
@flask_api.route("/random", methods=["GET"])
def get_random_story():
    """Retrieve a story from any scenario."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stories")
            total_rows = cursor.fetchone()["count"]
            random_index = random.randint(1, total_rows)

            logger.info("Random index selected: %s", random_index)

            cursor.execute("SELECT scenario, story_id FROM stories WHERE id = %s", (random_index,))
            result = cursor.fetchone()
            scenario, story_id = result["scenario"], result["story_id"]

            logger.info("Scenario: %s, Story ID: %s", scenario, story_id)

            cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (story_id,))
            story = cursor.fetchone()["story"]

            logger.info("Retrieved story")

            return flask.jsonify({"story": story})

options = {
    scenario: {
        "prompt": f"Please tell me the story of {scenario.capitalize()}.",
        "database": scenario
    }
    for scenario in scenarios
}

for scenario, details in options.items():
    flask_api.add_url_rule(f"/new-{scenario}", f"unlock_{scenario}_story",
                           lambda s=details["prompt"], d=details["database"]: unlock_story(s, d),
                           methods=["GET"])

@flask_api.route("/new-random", methods=["GET"])
def unlock_random_story():
    """Unlock a story from a random scenario."""
    random_selection = random.choice(list(options.keys()))
    prompt = options[random_selection]["prompt"]
    database = options[random_selection]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-user", methods=["POST"])
def unlock_guest_story():
    """Unlock a guest's story."""
    data = flask.request.get_json()

    scenario = "guest"

    if data:
        guest_entry = data.get("userInput").strip()
        if data.get("userType") in user_scenarios:
            scenario = data.get("userType")
    else:
        guest_entry = None

    if not guest_entry or len(guest_entry) > 999:
        return flask.jsonify({"error": "Invalid input"}), 400

    if scenario == "guest":
        return unlock_guest(request=guest_entry)
    if scenario in scenarios:
        return unlock_guest_scenario(request=guest_entry, scenario=scenario)
    if scenario == "random":
        random_scenario = random.choice(scenarios)
        return unlock_guest_scenario(request=guest_entry, scenario=random_scenario)

    return

@limiter.exempt
@flask_api.route("/terms")
def serve_terms():
    """Serve terms"""
    return flask.render_template("terms.html")

@limiter.exempt
@flask_api.route("/privacy")
def serve_privacy():
    """Serve privacy"""
    return flask.render_template("privacy.html")

@limiter.exempt
@flask_api.route("/robots.txt")
def serve_robots():
    """Serve robots.txt"""
    return flask.send_from_directory(
        static_path,
        "robots.txt"
    )

@limiter.exempt
@flask_api.route("/sitemap.xml")
def serve_sitemap():
    """Serve sitemap.xml"""
    return flask.send_from_directory(
        static_path,
        "sitemap.xml"
    )

@flask_api.before_request
def block_duplicated_parameters():
    """Block duplicated query parameters"""
    for _, values in flask.request.args.lists():
        if len(values) > 1:
            return flask.jsonify({"error": "Something went wrong."}), 400

@flask_api.after_request
def set_security_headers(response):
    """Set security headers"""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

if __name__ == "__main__":
    waitress.serve(flask_api, host="0.0.0.0", port=10000, threads=8)
