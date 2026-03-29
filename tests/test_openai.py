"""Tests for openai.py"""

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock

import flask
import pytest



MODULE_NAME = "app.src.integrations.openai"


def _clear_module():
    sys.modules.pop(MODULE_NAME, None)


class _FakeDictRow:
    pass


class _FakePsycopgModule:
    def __init__(self):
        self.connect = Mock(name="psycopg.connect")


class _FakePsycopgRowsModule:
    dict_row = _FakeDictRow


def _install_config_stub(monkeypatch):
    config_stub = types.ModuleType("app.config")
    config_stub.OPENAI_KEY = "test-key"
    config_stub.OPENAI_ORG = "test-org"
    config_stub.OPENAI_PROJECT = "test-project"
    config_stub.OPENAI_MODEL = "test-model"
    config_stub.POSTGRES_DB = "test-db"
    config_stub.POSTGRES_USER = "test-user"
    config_stub.POSTGRES_PASSWORD = "test-pass"
    config_stub.POSTGRES_HOST = "test-host"
    config_stub.POSTGRES_PORT = "5432"
    monkeypatch.setitem(sys.modules, "app.config", config_stub)
    return config_stub


def _install_psycopg_stub(monkeypatch):
    psycopg_stub = _FakePsycopgModule()
    psycopg_rows_stub = _FakePsycopgRowsModule()
    monkeypatch.setitem(sys.modules, "psycopg", psycopg_stub)
    monkeypatch.setitem(sys.modules, "psycopg.rows", psycopg_rows_stub)
    return psycopg_stub, psycopg_rows_stub


@pytest.fixture
def openai_module(monkeypatch):
    _install_config_stub(monkeypatch)
    _install_psycopg_stub(monkeypatch)
    _clear_module()
    return importlib.import_module(MODULE_NAME)


def _make_stream_chunk(text):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=text)
            )
        ]
    )


def _make_chat_response(text):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text)
            )
        ]
    )


class FakeCursor:
    def __init__(self, fetchone_results=None):
        self.fetchone_results = list(fetchone_results or [])
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if not self.fetchone_results:
            raise AssertionError("fetchone() called with no prepared results")
        return self.fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commit_called = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_called = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_db_connection_uses_expected_psycopg_parameters(openai_module, monkeypatch):
    connect_mock = Mock(return_value="db-connection")

    monkeypatch.setattr(openai_module.psycopg, "connect", connect_mock)
    monkeypatch.setattr(openai_module, "POSTGRES_DB", "db")
    monkeypatch.setattr(openai_module, "POSTGRES_USER", "user")
    monkeypatch.setattr(openai_module, "POSTGRES_PASSWORD", "pass")
    monkeypatch.setattr(openai_module, "POSTGRES_HOST", "host")
    monkeypatch.setattr(openai_module, "POSTGRES_PORT", "5432")

    result = openai_module.get_db_connection()

    assert result == "db-connection"
    connect_mock.assert_called_once_with(
        dbname="db",
        user="user",
        password="pass",
        host="host",
        port="5432",
        row_factory=openai_module.dict_row,
    )
    assert openai_module.dict_row is _FakeDictRow


def test_fetch_prompt_returns_instructions(openai_module, monkeypatch):
    cursor = FakeCursor(fetchone_results=[{"instructions": "system prompt"}])
    connection = FakeConnection(cursor)

    monkeypatch.setattr(openai_module, "get_db_connection", lambda: connection)

    result = openai_module.fetch_prompt(7)

    assert result == "system prompt"
    assert cursor.executed == [
        ("SELECT instructions FROM prompts WHERE id = %s", (7,))
    ]


def test_get_story_returns_random_story(openai_module, monkeypatch):
    cursor = FakeCursor(
        fetchone_results=[
            {"count": 10},
            {"story": "chosen story"},
        ]
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(openai_module, "get_db_connection", lambda: connection)
    monkeypatch.setattr(openai_module.random, "randint", lambda a, b: 4)

    app = flask.Flask(__name__)
    with app.app_context():
        response = openai_module.get_story("california")

    assert response.status_code == 200
    assert response.get_json() == {"story": "chosen story"}
    assert cursor.executed == [
        ("SELECT COUNT(*) FROM california", None),
        ("SELECT story FROM california WHERE id = %s", (4,)),
    ]


def test_unlock_story_streams_response_and_stores_story(openai_module, monkeypatch):
    first_stream = iter([
        _make_stream_chunk("Hello "),
        _make_stream_chunk(None),
        _make_stream_chunk("world"),
    ])

    create_mock = Mock(return_value=first_stream)
    client_instance = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    openai_ctor = Mock(return_value=client_instance)
    monkeypatch.setattr(openai_module, "OpenAI", openai_ctor)
    monkeypatch.setattr(openai_module, "fetch_prompt", Mock(return_value="system instructions"))
    monkeypatch.setattr(openai_module, "OPENAI_KEY", "key")
    monkeypatch.setattr(openai_module, "OPENAI_ORG", "org")
    monkeypatch.setattr(openai_module, "OPENAI_PROJECT", "project")
    monkeypatch.setattr(openai_module, "OPENAI_MODEL", "model-x")

    cursor = FakeCursor(fetchone_results=[{"id": 12}])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(openai_module, "get_db_connection", lambda: connection)

    app = flask.Flask(__name__)
    with app.test_request_context("/"):
        response = openai_module.unlock_story("tell me a story", "california")
        streamed = "".join(response.response)

    assert streamed == "Hello world"
    assert response.content_type == "text/plain; charset=utf-8"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"

    openai_ctor.assert_called_once_with(
        api_key="key",
        organization="org",
        project="project",
    )

    create_mock.assert_called_once_with(
        model="model-x",
        messages=[
            {"role": "system", "content": "system instructions"},
            {"role": "user", "content": "tell me a story"},
        ],
        stream=True,
    )

    assert cursor.executed == [
        ("INSERT INTO california (story) VALUES (%s) RETURNING id", ("Hello world",)),
        ("INSERT INTO stories (scenario, story_id) VALUES (%s, %s)", ("california", 12)),
    ]
    assert connection.commit_called is True


def test_unlock_guest_uses_fallback_prompt_when_profile_prompt_missing(openai_module, monkeypatch):
    first_response = _make_chat_response("guest profile")
    second_stream = iter([
        _make_stream_chunk("Once "),
        _make_stream_chunk("upon a time"),
    ])

    create_mock = Mock(side_effect=[first_response, second_stream])
    client_instance = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    monkeypatch.setattr(openai_module, "OpenAI", Mock(return_value=client_instance))
    monkeypatch.setattr(openai_module, "fetch_prompt", Mock(side_effect=[None, "story instructions"]))
    monkeypatch.setattr(openai_module, "OPENAI_MODEL", "model-y")

    cursor = FakeCursor(fetchone_results=[{"id": 22}])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(openai_module, "get_db_connection", lambda: connection)

    app = flask.Flask(__name__)
    with app.test_request_context("/"):
        response = openai_module.unlock_guest("about me")
        streamed = "".join(response.response)

    assert streamed == "Once upon a time"

    assert create_mock.call_args_list[0].kwargs == {
        "model": "model-y",
        "messages": [
            {"role": "system", "content": "Our guest is lost in the ether."},
            {"role": "user", "content": "about me"},
        ],
        "stream": False,
    }

    assert create_mock.call_args_list[1].kwargs == {
        "model": "model-y",
        "messages": [
            {"role": "system", "content": "story instructions"},
            {"role": "user", "content": "guest profile"},
        ],
        "stream": True,
    }

    assert cursor.executed == [
        ("INSERT INTO guest (story) VALUES (%s) RETURNING id", ("Once upon a time",)),
    ]
    assert connection.commit_called is True


def test_unlock_guest_scenario_returns_fallback_string_when_profile_prompt_missing(openai_module, monkeypatch):
    monkeypatch.setattr(openai_module, "fetch_prompt", Mock(return_value=None))

    result = openai_module.unlock_guest_scenario("about me", "israel")

    assert result == "Our guest is lost in the ether."


def test_unlock_guest_scenario_streams_story_and_stores_guest_story(openai_module, monkeypatch):
    first_response = _make_chat_response("guest profile")
    second_stream = iter([
        _make_stream_chunk("Scenario "),
        _make_stream_chunk("story"),
    ])

    create_mock = Mock(side_effect=[first_response, second_stream])
    client_instance = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_mock)
        )
    )

    monkeypatch.setattr(openai_module, "OpenAI", Mock(return_value=client_instance))
    monkeypatch.setattr(
        openai_module,
        "fetch_prompt",
        Mock(side_effect=[
            "guest profiling instructions",
            "start instructions",
            "end instructions",
        ]),
    )
    monkeypatch.setattr(openai_module.random, "randint", lambda a, b: 3)
    monkeypatch.setattr(openai_module, "OPENAI_MODEL", "model-z")

    scenario_cursor = FakeCursor(fetchone_results=[{"count": 8}, {"story": "seed scenario story"}])
    scenario_connection = FakeConnection(scenario_cursor)

    insert_cursor = FakeCursor(fetchone_results=[{"id": 31}])
    insert_connection = FakeConnection(insert_cursor)

    connections = iter([scenario_connection, insert_connection])
    monkeypatch.setattr(openai_module, "get_db_connection", lambda: next(connections))

    app = flask.Flask(__name__)
    with app.test_request_context("/"):
        response = openai_module.unlock_guest_scenario("who am i", "otherworld")
        streamed = "".join(response.response)

    assert streamed == "Scenario story"

    assert scenario_cursor.executed == [
        ("SELECT COUNT(*) FROM otherworld", None),
        ("SELECT story FROM otherworld WHERE id = %s", (3,)),
    ]

    assert create_mock.call_args_list[0].kwargs == {
        "model": "model-z",
        "messages": [
            {"role": "system", "content": "guest profiling instructions"},
            {"role": "user", "content": "who am i"},
        ],
        "stream": False,
    }

    assert create_mock.call_args_list[1].kwargs == {
        "model": "model-z",
        "messages": [
            {
                "role": "system",
                "content": "start instructions\nseed scenario story\nend instructions",
            },
            {"role": "user", "content": "guest profile"},
        ],
        "stream": True,
    }

    assert insert_cursor.executed == [
        ("INSERT INTO guest (story) VALUES (%s) RETURNING id", ("Scenario story",)),
    ]
    assert insert_connection.commit_called is True
