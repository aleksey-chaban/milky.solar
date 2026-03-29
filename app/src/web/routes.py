"""API Endpoints"""

import random

import flask

from app.config import (
    limiter,
    flask_api,
    static_path,
)

from app.src.services.selectors import (
    SCENARIOS,
    USER_SCENARIOS,
    OPTIONS,
)

from app.src.integrations.openai import (
    get_db_connection,
    unlock_story,
    unlock_guest,
    unlock_guest_scenario
)


@limiter.exempt
@flask_api.route("/")
def home():
    """Render the home page."""

    return flask.render_template("index.html")


@limiter.exempt
@flask_api.route("/random", methods=["GET"])
def get_random_story():
    """Retrieve a story from any scenario."""

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stories")
            total_rows = cursor.fetchone()["count"]
            random_index = random.randint(1, total_rows)

            print(f"Random index selected: {random_index}")

            cursor.execute("SELECT scenario, story_id FROM stories WHERE id = %s", (random_index,))
            result = cursor.fetchone()
            scenario, story_id = result["scenario"], result["story_id"]

            print(f"Scenario: {scenario}, Story ID: {story_id}")

            cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (story_id,))
            story = cursor.fetchone()["story"]

            print("Retrieved story")

            return flask.jsonify({"story": story})


@flask_api.route("/new-random", methods=["GET"])
def unlock_random_story():
    """Unlock a story from a random scenario."""

    random_selection = random.choice(list(OPTIONS.keys()))
    prompt = OPTIONS[random_selection]["prompt"]
    database = OPTIONS[random_selection]["database"]

    return unlock_story(request=prompt, database=database)


@flask_api.route("/new-user", methods=["POST"])
def unlock_guest_story():
    """Unlock a guest's story."""

    data = flask.request.get_json()

    scenario = "guest"

    if data:
        guest_entry = data.get("userInput").strip()
        if data.get("userType") in USER_SCENARIOS:
            scenario = data.get("userType")
    else:
        guest_entry = None

    if not guest_entry or len(guest_entry) > 999:
        return flask.jsonify({"error": "Invalid input"}), 400

    if scenario == "guest":
        return unlock_guest(request=guest_entry)
    if scenario in SCENARIOS:
        return unlock_guest_scenario(request=guest_entry, scenario=scenario)
    if scenario == "random":
        random_scenario = random.choice(SCENARIOS)
        return unlock_guest_scenario(request=guest_entry, scenario=random_scenario)


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
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains; preload"
    )

    return response
