"""Serve website"""

import random

import psycopg
from psycopg.rows import dict_row

import flask
from flask import Response, stream_with_context

from openai import OpenAI

from app.config import (
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

            print(f"{scenario} index selected: {random_id}")

            cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (random_id,))
            story = cursor.fetchone()["story"]

            print("Retrieved story")

            return flask.jsonify({"story": story})

def unlock_story(request, database):
    """Unlock a story."""

    client = OpenAI(
        api_key=OPENAI_KEY,
        organization=OPENAI_ORG,
        project=OPENAI_PROJECT
    )

    system_instructions = fetch_prompt(1)

    print("Gathered instructions")

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

            print(f"Stored {database} scenario {story_id}")

        print("Retrieved story")


    return Response(
        stream_with_context(generate()),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def unlock_guest(request):
    """Unlock a guest story."""

    client = OpenAI(
        api_key=OPENAI_KEY,
        organization=OPENAI_ORG,
        project=OPENAI_PROJECT
    )

    system_instructions = fetch_prompt(2)

    if not system_instructions:
        system_instructions = "Our guest is lost in the ether."

    print("Gathered instructions")

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

        print("Gathered profile")

        system_instructions = fetch_prompt(3)

        print("Gathered instructions")

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

            print(f"Stored guest scenario {story_id}")

        print("Retrieved story")

    return Response(
        stream_with_context(generate(system_instructions=system_instructions)),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def unlock_guest_scenario(request, scenario):
    """Unlock a guest scenario."""

    client = OpenAI(
        api_key=OPENAI_KEY,
        organization=OPENAI_ORG,
        project=OPENAI_PROJECT
    )

    system_instructions = fetch_prompt(2)

    if not system_instructions:
        system_instructions = "Our guest is lost in the ether."
        return system_instructions

    print("Gathered instructions")

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

        print("Gathered profile")

        start_system_instructions = fetch_prompt(4)

        print("Gathered instructions")

        end_system_instructions = fetch_prompt(5)

        print("Gathered instructions")

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {scenario}")
                total_rows = cursor.fetchone()["count"]
                random_id = random.randint(1, total_rows)

                print(f"{scenario} index selected: {random_id}")

                cursor.execute(f"SELECT story FROM {scenario} WHERE id = %s", (random_id,))
                story = cursor.fetchone()["story"]

        print("Retrieved story")

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

            print(f"Stored guest scenario {story_id}")

        print("Retrieved story")


    return Response(
        stream_with_context(generate(system_instructions=system_instructions)),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
