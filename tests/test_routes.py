"""Tests for routes.py"""

import importlib
import sys
import types
from contextlib import contextmanager
from unittest.mock import Mock

import flask
import pytest


MODULE_NAME = "app.src.web.routes"


def _clear_module():
    sys.modules.pop(MODULE_NAME, None)


class _FakeLimiter:
    def exempt(self, func):
        return func


class _FakeFlaskAPI(flask.Flask):
    def __init__(self):
        super().__init__("test_routes")


def _install_config_stub(monkeypatch):
    config_stub = types.ModuleType("app.config")
    config_stub.limiter = _FakeLimiter()
    config_stub.flask_api = _FakeFlaskAPI()
    config_stub.static_path = "/tmp/static"
    monkeypatch.setitem(sys.modules, "app.config", config_stub)
    return config_stub


def _install_selectors_stub(monkeypatch):
    selectors_stub = types.ModuleType("app.src.services.selectors")
    selectors_stub.SCENARIOS = ["israel", "australia", "newzealand", "otherworld", "california", "unitedkingdom"]
    selectors_stub.USER_SCENARIOS = ["guest", "israel", "australia", "newzealand", "otherworld", "california", "unitedkingdom", "random"]
    selectors_stub.OPTIONS = {
        scenario: {
            "prompt": f"Please tell me the story of {scenario.capitalize()}.",
            "database": scenario,
        }
        for scenario in selectors_stub.SCENARIOS
    }
    monkeypatch.setitem(sys.modules, "app.src.services.selectors", selectors_stub)
    return selectors_stub


def _install_openai_stub(monkeypatch):
    openai_stub = types.ModuleType("app.src.integrations.openai")

    def _unused_get_db_connection():
        raise AssertionError("get_db_connection should be stubbed in this test")

    def _unused_unlock_story(*args, **kwargs):
        raise AssertionError("unlock_story should be stubbed in this test")

    def _unused_unlock_guest(*args, **kwargs):
        raise AssertionError("unlock_guest should be stubbed in this test")

    def _unused_unlock_guest_scenario(*args, **kwargs):
        raise AssertionError("unlock_guest_scenario should be stubbed in this test")

    openai_stub.get_db_connection = _unused_get_db_connection
    openai_stub.unlock_story = _unused_unlock_story
    openai_stub.unlock_guest = _unused_unlock_guest
    openai_stub.unlock_guest_scenario = _unused_unlock_guest_scenario
    monkeypatch.setitem(sys.modules, "app.src.integrations.openai", openai_stub)
    return openai_stub


@pytest.fixture
def routes_module(monkeypatch):
    _install_config_stub(monkeypatch)
    _install_selectors_stub(monkeypatch)
    _install_openai_stub(monkeypatch)
    _clear_module()
    module = importlib.import_module(MODULE_NAME)
    return module


@pytest.fixture
def app(routes_module):
    routes_module.flask_api.config["TESTING"] = True
    return routes_module.flask_api


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_renders_index(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module.flask, "render_template", lambda name: f"rendered:{name}")

    response = client.get("/")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered:index.html"


def test_get_random_story_returns_story(client, routes_module, monkeypatch):
    executed = []

    class FakeCursor:
        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchone(self):
            query, _ = executed[-1]
            if query == "SELECT COUNT(*) FROM stories":
                return {"count": 10}
            if query == "SELECT scenario, story_id FROM stories WHERE id = %s":
                return {"scenario": "space", "story_id": 3}
            if query == "SELECT story FROM space WHERE id = %s":
                return {"story": "A story from space"}
            raise AssertionError(f"Unexpected query: {query}")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    @contextmanager
    def fake_get_db_connection():
        yield FakeConnection()

    monkeypatch.setattr(routes_module, "get_db_connection", fake_get_db_connection)
    monkeypatch.setattr(routes_module.random, "randint", lambda a, b: 4)

    response = client.get("/random")

    assert response.status_code == 200
    assert response.get_json() == {"story": "A story from space"}
    assert executed == [
        ("SELECT COUNT(*) FROM stories", None),
        ("SELECT scenario, story_id FROM stories WHERE id = %s", (4,)),
        ("SELECT story FROM space WHERE id = %s", (3,)),
    ]


def test_unlock_random_story_uses_random_option(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module, "OPTIONS", {
        "alpha": {"prompt": "prompt-a", "database": "db-a"},
        "beta": {"prompt": "prompt-b", "database": "db-b"},
    })
    monkeypatch.setattr(routes_module.random, "choice", lambda values: "beta")

    def _unlock_story_response(**kwargs):
        return flask.jsonify({"ok": True, "path": "random"})

    unlock_story_mock = Mock(side_effect=_unlock_story_response)
    monkeypatch.setattr(routes_module, "unlock_story", unlock_story_mock)

    response = client.get("/new-random")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "path": "random"}
    unlock_story_mock.assert_called_once_with(request="prompt-b", database="db-b")


def test_unlock_guest_story_rejects_missing_json(client):
    response = client.post("/new-user", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid input"}


def test_unlock_guest_story_rejects_blank_input(client):
    response = client.post("/new-user", json={"userInput": "   ", "userType": "guest"})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid input"}


def test_unlock_guest_story_rejects_too_long_input(client):
    response = client.post(
        "/new-user",
        json={"userInput": "x" * 1000, "userType": "guest"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid input"}


def test_unlock_guest_story_calls_unlock_guest_for_default_scenario(client, routes_module, monkeypatch):
    def _unlock_guest_response(**kwargs):
        return flask.jsonify({"ok": True, "path": "guest"})

    unlock_guest_mock = Mock(side_effect=_unlock_guest_response)
    monkeypatch.setattr(routes_module, "unlock_guest", unlock_guest_mock)
    monkeypatch.setattr(routes_module, "USER_SCENARIOS", {"guest", "random", "space"})
    monkeypatch.setattr(routes_module, "SCENARIOS", ["space", "ocean"])

    response = client.post(
        "/new-user",
        json={"userInput": "hello world", "userType": "guest"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "path": "guest"}
    unlock_guest_mock.assert_called_once_with(request="hello world")


def test_unlock_guest_story_calls_unlock_guest_when_user_type_is_not_allowed(client, routes_module, monkeypatch):
    def _unlock_guest_response(**kwargs):
        return flask.jsonify({"ok": True})

    unlock_guest_mock = Mock(side_effect=_unlock_guest_response)
    monkeypatch.setattr(routes_module, "unlock_guest", unlock_guest_mock)
    monkeypatch.setattr(routes_module, "USER_SCENARIOS", {"guest", "random"})
    monkeypatch.setattr(routes_module, "SCENARIOS", ["space"])

    response = client.post(
        "/new-user",
        json={"userInput": "hello world", "userType": "not-valid"},
    )

    assert response.status_code == 200
    unlock_guest_mock.assert_called_once_with(request="hello world")


def test_unlock_guest_story_calls_unlock_guest_scenario_for_named_scenario(client, routes_module, monkeypatch):
    def _unlock_guest_scenario_response(**kwargs):
        return flask.jsonify({"ok": True, "path": "scenario"})

    unlock_guest_scenario_mock = Mock(side_effect=_unlock_guest_scenario_response)
    monkeypatch.setattr(routes_module, "unlock_guest_scenario", unlock_guest_scenario_mock)
    monkeypatch.setattr(routes_module, "USER_SCENARIOS", {"guest", "space"})
    monkeypatch.setattr(routes_module, "SCENARIOS", ["space", "ocean"])

    response = client.post(
        "/new-user",
        json={"userInput": "hello world", "userType": "space"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "path": "scenario"}
    unlock_guest_scenario_mock.assert_called_once_with(
        request="hello world",
        scenario="space",
    )


def test_unlock_guest_story_calls_random_scenario_when_requested(client, routes_module, monkeypatch):
    def _unlock_guest_scenario_response(**kwargs):
        return flask.jsonify({"ok": True, "path": "random-scenario"})

    unlock_guest_scenario_mock = Mock(side_effect=_unlock_guest_scenario_response)
    monkeypatch.setattr(routes_module, "unlock_guest_scenario", unlock_guest_scenario_mock)
    monkeypatch.setattr(routes_module, "USER_SCENARIOS", {"guest", "random"})
    monkeypatch.setattr(routes_module, "SCENARIOS", ["space", "ocean"])
    monkeypatch.setattr(routes_module.random, "choice", lambda values: "ocean")

    response = client.post(
        "/new-user",
        json={"userInput": "hello world", "userType": "random"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "path": "random-scenario"}
    unlock_guest_scenario_mock.assert_called_once_with(
        request="hello world",
        scenario="ocean",
    )


def test_terms_renders_terms_template(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module.flask, "render_template", lambda name: f"rendered:{name}")

    response = client.get("/terms")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered:terms.html"


def test_privacy_renders_privacy_template(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module.flask, "render_template", lambda name: f"rendered:{name}")

    response = client.get("/privacy")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered:privacy.html"


def test_serve_robots_sends_static_file(client, routes_module, monkeypatch):
    send_mock = Mock(return_value=flask.Response("robots", status=200))
    monkeypatch.setattr(routes_module.flask, "send_from_directory", send_mock)
    monkeypatch.setattr(routes_module, "static_path", "/tmp/static")

    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "robots"
    send_mock.assert_called_once_with("/tmp/static", "robots.txt")


def test_serve_sitemap_sends_static_file(client, routes_module, monkeypatch):
    send_mock = Mock(return_value=flask.Response("sitemap", status=200))
    monkeypatch.setattr(routes_module.flask, "send_from_directory", send_mock)
    monkeypatch.setattr(routes_module, "static_path", "/tmp/static")

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "sitemap"
    send_mock.assert_called_once_with("/tmp/static", "sitemap.xml")


def test_block_duplicated_parameters_rejects_duplicate_query_values(client):
    response = client.get("/?x=1&x=2")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Something went wrong."}


def test_block_duplicated_parameters_allows_unique_query_values(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module.flask, "render_template", lambda name: f"rendered:{name}")

    response = client.get("/?x=1&y=2")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered:index.html"


def test_set_security_headers_are_added(client, routes_module, monkeypatch):
    monkeypatch.setattr(routes_module.flask, "render_template", lambda name: f"rendered:{name}")

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == (
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
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Strict-Transport-Security"] == (
        "max-age=63072000; includeSubDomains; preload"
    )
