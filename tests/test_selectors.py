"""Tests for selectors.py"""

import importlib
import sys
import types
from unittest.mock import Mock


MODULE_NAME = "app.src.services.selectors"


def _clear_module():
    sys.modules.pop(MODULE_NAME, None)


def _install_config_stub(monkeypatch, limiter=None, flask_api=None):
    config_stub = types.ModuleType("app.config")
    config_stub.limiter = limiter if limiter is not None else Mock()
    config_stub.flask_api = flask_api if flask_api is not None else Mock()
    monkeypatch.setitem(sys.modules, "app.config", config_stub)
    return config_stub


def _install_openai_stub(monkeypatch, get_story_impl=None, unlock_story_impl=None):
    openai_stub = types.ModuleType("app.src.integrations.openai")
    openai_stub.get_story = get_story_impl or Mock()
    openai_stub.unlock_story = unlock_story_impl or Mock()
    monkeypatch.setitem(sys.modules, "app.src.integrations.openai", openai_stub)
    return openai_stub


def test_scenarios_and_user_scenarios_are_defined(monkeypatch):
    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            pass

    _install_openai_stub(monkeypatch)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())
    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    assert module.SCENARIOS == [
        "israel",
        "australia",
        "newzealand",
        "otherworld",
        "california",
        "unitedkingdom",
    ]

    assert module.USER_SCENARIOS == [
        "guest",
        "israel",
        "australia",
        "newzealand",
        "otherworld",
        "california",
        "unitedkingdom",
        "random",
    ]


def test_options_are_built_from_scenarios(monkeypatch):
    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            pass

    _install_openai_stub(monkeypatch)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())
    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    assert module.OPTIONS == {
        "israel": {
            "prompt": "Please tell me the story of Israel.",
            "database": "israel",
        },
        "australia": {
            "prompt": "Please tell me the story of Australia.",
            "database": "australia",
        },
        "newzealand": {
            "prompt": "Please tell me the story of Newzealand.",
            "database": "newzealand",
        },
        "otherworld": {
            "prompt": "Please tell me the story of Otherworld.",
            "database": "otherworld",
        },
        "california": {
            "prompt": "Please tell me the story of California.",
            "database": "california",
        },
        "unitedkingdom": {
            "prompt": "Please tell me the story of Unitedkingdom.",
            "database": "unitedkingdom",
        },
    }


def test_story_routes_are_registered_for_each_scenario(monkeypatch):
    registrations = []

    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            registrations.append(
                {
                    "rule": rule,
                    "endpoint": endpoint,
                    "view_func": view_func,
                    "methods": methods,
                }
            )

    _install_openai_stub(monkeypatch)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())

    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    get_route_registrations = [
        item for item in registrations
        if item["endpoint"] and item["endpoint"].startswith("get_")
    ]

    assert len(get_route_registrations) == len(module.SCENARIOS)

    for scenario in module.SCENARIOS:
        matching = [
            item for item in get_route_registrations
            if item["rule"] == f"/{scenario}"
            and item["endpoint"] == f"get_{scenario}_story"
            and item["methods"] == ["GET"]
        ]
        assert len(matching) == 1


def test_story_route_calls_get_story_with_bound_scenario(monkeypatch):
    registered_view_functions = {}

    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            registered_view_functions[endpoint] = view_func

    get_story_mock = Mock(return_value={"story": "ok"})

    _install_openai_stub(monkeypatch, get_story_impl=get_story_mock)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())

    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    for scenario in module.SCENARIOS:
        get_story_mock.reset_mock()

        result = registered_view_functions[f"get_{scenario}_story"]()

        assert result == {"story": "ok"}
        get_story_mock.assert_called_once_with(scenario)


def test_story_routes_are_exempted_from_limiter(monkeypatch):
    exempted_functions = []
    registered_view_functions = {}

    class FakeLimiter:
        def exempt(self, func):
            exempted_functions.append(func)
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            registered_view_functions[endpoint] = view_func

    _install_openai_stub(monkeypatch)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())

    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    assert len(exempted_functions) == len(module.SCENARIOS)

    for scenario in module.SCENARIOS:
        assert f"get_{scenario}_story" in registered_view_functions


def test_unlock_routes_are_registered_for_each_option(monkeypatch):
    registrations = []

    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            registrations.append(
                {
                    "rule": rule,
                    "endpoint": endpoint,
                    "view_func": view_func,
                    "methods": methods,
                }
            )

    _install_openai_stub(monkeypatch)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())

    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    unlock_route_registrations = [
        item for item in registrations
        if item["endpoint"] and item["endpoint"].startswith("unlock_")
    ]

    assert len(unlock_route_registrations) == len(module.SCENARIOS)

    for scenario in module.SCENARIOS:
        matching = [
            item for item in unlock_route_registrations
            if item["rule"] == f"/new-{scenario}"
            and item["endpoint"] == f"unlock_{scenario}_story"
            and item["methods"] == ["GET"]
        ]
        assert len(matching) == 1


def test_unlock_route_calls_unlock_story_with_bound_prompt_and_database(monkeypatch):
    registered_view_functions = {}

    class FakeLimiter:
        def exempt(self, func):
            return func

    class FakeFlaskAPI:
        def add_url_rule(self, rule, endpoint, view_func, methods=None):
            registered_view_functions[endpoint] = view_func

    unlock_story_mock = Mock(return_value={"status": "ok"})

    _install_openai_stub(monkeypatch, unlock_story_impl=unlock_story_mock)
    _install_config_stub(monkeypatch, FakeLimiter(), FakeFlaskAPI())

    _clear_module()
    module = importlib.import_module(MODULE_NAME)

    for scenario, details in module.OPTIONS.items():
        unlock_story_mock.reset_mock()

        result = registered_view_functions[f"unlock_{scenario}_story"]()

        assert result == {"status": "ok"}
        unlock_story_mock.assert_called_once_with(
            details["prompt"],
            details["database"],
        )
