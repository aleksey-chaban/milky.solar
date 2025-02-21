"""Serve website"""

import logging
import os
import random

import psycopg2
from psycopg2.extras import DictCursor

from logging.handlers import RotatingFileHandler

import flask
import waitress

from openai import OpenAI

log_path = os.path.join(os.getcwd(), "logs", "site.log")

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

POSTGRES_DB = os.getenv("postgres_milky_solar_db")
POSTGRES_USER = os.getenv("postgres_milky_solar_user")
POSTGRES_PASSWORD = os.getenv("postgres_milky_solar_pass")
POSTGRES_HOST = os.getenv("postgres_milky_solar_host")
POSTGRES_PORT = os.getenv("postgres_milky_solar_port")

def get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        cursor_factory=DictCursor
    )


def get_story(scenario):
    """Retrieve a story from the specified scenario."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {scenario}")
            total_rows = cursor.fetchone()[0]
            random_id = random.randint(1, total_rows)

            logger.info("%s index selected: %s", scenario, random_id)

            cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (random_id,))
            story = cursor.fetchone()["story"]

            logger.info("Retrieved story")

            return flask.jsonify({"story": story})

def unlock_story(request, database):
    """Unlock a story."""
    logger.info("Unlocking scenario")

    openai_key = os.getenv("openai_milky_solar_key")
    openai_org = os.getenv("openai_milky_solar_org")
    openai_project = os.getenv("openai_milky_solar_project")

    try:
        client = OpenAI(
            api_key=openai_key,
            organization=openai_org,
            project=openai_project
        )
    except Exception as e:
        logger.error("Server error: %s", e)
        raise e

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT instructions FROM prompts WHERE id = 1")
            system_instructions = cursor.fetchone()["instructions"]

    logger.info("Gathered instructions")

    response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
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
        ]
    )

    story = response.choices[0].message.content

    logger.info("Discovered scenario")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"INSERT INTO {database} (story) VALUES (%s) RETURNING id", (story,))
            story_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO stories (scenario, story_id) VALUES (%s, %s)", (database, story_id))

            logger.info("Unlocked %s scenario %s", database, story_id)

        connection.commit()

    logger.info("Retrieved story")

    return flask.jsonify({"story": story})

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
    "finland",
    "unitedkingdom"
]
for scenario in scenarios:
    flask_api.add_url_rule(f"/{scenario}", f"get_{scenario}_story", lambda s=scenario: get_story(s), methods=["GET"])


@flask_api.route("/random", methods=["GET"])
def get_random_story():
    """Retrieve a story from any scenario."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stories")
            total_rows = cursor.fetchone()[0]
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

@flask_api.route("/robots.txt")
def serve_robots():
    """Serve robots.txt"""
    return flask.send_from_directory(
        static_path,
        "robots.txt"
    )

@flask_api.route("/sitemap.xml")
def serve_sitemap():
    """Serve sitemap.xml"""
    return flask.send_from_directory(
        static_path,
        "sitemap.xml"
    )

if __name__ == "__main__":
    waitress.serve(flask_api, host="0.0.0.0", port=10000, threads=8)
