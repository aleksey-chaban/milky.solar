"""Serve website"""

import logging
import os
import random
import contextlib
import sqlite3

from logging.handlers import RotatingFileHandler

import flask
import waitress

from openai import OpenAI

log_path = os.path.join(os.getcwd(), "logs", "site.log")

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
database_path = os.path.join(os.getcwd(), "instance", "stories.db")

flask_api = flask.Flask(
    __name__,
    static_folder=static_path,
    template_folder=template_path
)

def get_story(scenario):
    """Retrieve a story from the specified scenario."""
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        with contextlib.closing(connection.cursor()) as cursor:
            query = f"SELECT COUNT(*) FROM {scenario}"
            cursor.execute(query)
            total_rows = cursor.fetchone()[0]
            random_id = random.randint(1, total_rows)

            logger.info("%s index selected: %s", scenario, random_id)

            query = f"SELECT story FROM {scenario} WHERE id = ?"
            cursor.execute(query, (random_id,))
            story = cursor.fetchone()["story"]

            logger.info("Retrieved story")

            return flask.jsonify({"story": story})

def unlock_story(request, database):
    """Unlock a Story"""
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
        logger.info("Server error: %s", e)
        raise e

    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        with contextlib.closing(connection.cursor()) as cursor:
            cursor.execute("SELECT instructions FROM prompts WHERE id = 1")
            system_instructions = cursor.fetchone()["instructions"]

    logger.info("Gathered instructions")

    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        with contextlib.closing(connection.cursor()) as cursor:
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

            query = f"INSERT INTO {database} (story) VALUES (?)"
            cursor.execute(query, (story,))
            story_id = cursor.lastrowid
            query = "INSERT INTO stories (scenario, story_id) VALUES (?, ?)"
            cursor.execute(query, (database, story_id,))

            logger.info("Unlocked %s scenario %s", database, story_id)

        connection.commit()

    logger.info("Retrieved story")

    return flask.jsonify({"story": story})

@flask_api.route("/")
def home():
    """Render the home page."""
    return flask.render_template("index.html")

@flask_api.route("/israel", methods=["GET"])
def get_israel_story():
    """Retrieve a story from the Israel scenario."""
    return get_story("israel")

@flask_api.route("/australia", methods=["GET"])
def get_australia_story():
    """Retrieve a story from the Australia scenario."""
    return get_story("australia")

@flask_api.route("/newzealand", methods=["GET"])
def get_newzealand_story():
    """Retrieve a story from the New Zealand scenario."""
    return get_story("newzealand")

@flask_api.route("/otherworld", methods=["GET"])
def get_otherworld_story():
    """Retrieve a story from the Otherworld scenario."""
    return get_story("otherworld")

@flask_api.route("/california", methods=["GET"])
def get_california_story():
    """Retrieve a story from the California scenario."""
    return get_story("california")

@flask_api.route("/finland", methods=["GET"])
def get_finland_story():
    """Retrieve a story from the Finland scenario."""
    return get_story("finland")

@flask_api.route("/unitedkingdom", methods=["GET"])
def get_unitedkingdom_story():
    """Retrieve a story from the United Kingdom scenario."""
    return get_story("unitedkingdom")

@flask_api.route("/random", methods=["GET"])
def get_random_story():
    """Retrieve a story from any scenario."""
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        with contextlib.closing(connection.cursor()) as cursor:
            query = "SELECT COUNT(*) FROM stories"
            cursor.execute(query)
            total_rows = cursor.fetchone()[0]
            random_index = random.randint(1, total_rows)

            logger.info("Random index selected: %s", random_index)

            query = "SELECT scenario, story_id FROM stories WHERE id = ?"
            cursor.execute(query, (random_index,))
            result = cursor.fetchone()
            scenario, story_id = result["scenario"], result["story_id"]

            logger.info("Scenario: %s, Story ID: %s", scenario, story_id)

            query = f"SELECT story FROM {scenario} WHERE id = ?"
            cursor.execute(query, (story_id,))
            story = cursor.fetchone()["story"]

            logger.info("Retrieved story")

            return flask.jsonify({"story": story})

options = {
    "israel": {
        "prompt": "Please tell me the story of Israel.",
        "database": "israel"
    },
    "australia": {
        "prompt": "Please tell me the story of Australia.",
        "database": "australia"
    },
    "newzealand": {
        "prompt": "Please tell me the story of New Zealand, South America.",
        "database": "newzealand"
    },
    "otherworld": {
        "prompt": "Please tell me the story of Otherworld.",
        "database": "otherworld"
    },
    "california": {
        "prompt": "Please tell me the story of New Zealand, Washington State, California.",
        "database": "california"
    },
    "finland": {
        "prompt": "Please tell me the story of Finland.",
        "database": "finland"
    },
    "unitedkingdom": {
        "prompt": "Please tell me the story of United Kingdom.",
        "database": "unitedkingdom"
    }
}

@flask_api.route("/new-israel", methods=["GET"])
def unlock_israel_story():
    """Unlock a story from the Israel scenario."""
    prompt = options["israel"]["prompt"]
    database = options["israel"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-australia", methods=["GET"])
def unlock_australia_story():
    """Unlock a story from the Australia scenario."""
    prompt = options["australia"]["prompt"]
    database = options["australia"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-newzealand", methods=["GET"])
def unlock_newzealand_story():
    """Unlock a story from the New Zealand scenario."""
    prompt = options["newzealand"]["prompt"]
    database = options["newzealand"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-otherworld", methods=["GET"])
def unlock_otherworld_story():
    """Unlock a story from the Otherworld scenario."""
    prompt = options["otherworld"]["prompt"]
    database = options["otherworld"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-california", methods=["GET"])
def unlock_california_story():
    """Unlock a story from the California scenario."""
    prompt = options["california"]["prompt"]
    database = options["california"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-finland", methods=["GET"])
def unlock_finland_story():
    """Unlock a story from the Finland scenario."""
    prompt = options["finland"]["prompt"]
    database = options["finland"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-unitedkingdom", methods=["GET"])
def unlock_unitedkingdom_story():
    """Unlock a story from the United Kingdom scenario."""
    prompt = options["unitedkingdom"]["prompt"]
    database = options["unitedkingdom"]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route("/new-random", methods=["GET"])
def unlock_random_story():
    """Unlock a story from a random scenario."""
    random_selection = random.choice(list(options.keys()))
    prompt = options[random_selection]["prompt"]
    database = options[random_selection]["database"]
    return unlock_story(request=prompt, database=database)

@flask_api.route('/robots.txt')
def serve_robots():
    """"Serve robots.txt"""
    return flask.send_from_directory(
        static_path,
        "robots.txt"
    )

@flask_api.route('/sitemap.xml')
def serve_sitemap():
    """"Serve sitemap.xml"""
    return flask.send_from_directory(
        static_path,
        "sitemap.xml"
    )

if __name__ == "__main__":
    waitress.serve(flask_api, host="0.0.0.0", port=8080, threads=8)
