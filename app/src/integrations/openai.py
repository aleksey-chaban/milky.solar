"""Serve website"""

import random

import psycopg
from psycopg.rows import dict_row

import flask
from flask import Response

from openai import OpenAI

from app.config import (
    logger,
    OPENAI_KEY,
    OPENAI_ORG,
    OPENAI_PROJECT,
    OPENAI_MODEL,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_HOST,
    POSTGRES_PORT,
)


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
                cursor.execute(
                    f"INSERT INTO {database} (story) VALUES (%s) RETURNING id",
                    (story_content,)
                )
                story_id = cursor.fetchone()["id"]

                cursor.execute(
                    "INSERT INTO stories (scenario, story_id) VALUES (%s, %s)",
                    (database, story_id)
                )

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
                cursor.execute(
                    "INSERT INTO guest (story) VALUES (%s) RETURNING id",
                    (story_content,)
                )
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
                cursor.execute(
                    "INSERT INTO guest (story) VALUES (%s) RETURNING id",
                    (story_content,)
                )
                story_id = cursor.fetchone()["id"]

                connection.commit()

            logger.info("Stored guest scenario %s", story_id)

        logger.info("Retrieved story")


    return Response(generate(system_instructions=system_instructions), content_type="text/plain")
