"""Tests for config.py"""

import importlib
import os
import sys
from types import SimpleNamespace

import pytest
import redis


MODULE_NAME = "app.config"


def _clear_config_module():
    sys.modules.pop(MODULE_NAME, None)


def _set_required_env(monkeypatch):
    monkeypatch.setenv("upstash_milky_solar_redis", "redis://localhost:6379/0")
    monkeypatch.setenv("openai_milky_solar_key", "test-key")
    monkeypatch.setenv("openai_milky_solar_org", "test-org")
    monkeypatch.setenv("openai_milky_solar_project", "test-project")
    monkeypatch.setenv("openai_milky_solar_model", "test-model")
    monkeypatch.setenv("postgres_milky_solar_db", "test-db")
    monkeypatch.setenv("postgres_milky_solar_user", "test-user")
    monkeypatch.setenv("postgres_milky_solar_pass", "test-pass")
    monkeypatch.setenv("postgres_milky_solar_host", "test-host")
    monkeypatch.setenv("postgres_milky_solar_port", "5432")


def _import_config(monkeypatch, *, redis_client=None, limiter_cls=None):
    _clear_config_module()
    _set_required_env(monkeypatch)

    if redis_client is None:
        redis_client = SimpleNamespace(ping=lambda: None)

    if limiter_cls is None:
        class FakeLimiter:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        limiter_cls = FakeLimiter

    monkeypatch.setattr("redis.from_url", lambda url: redis_client)
    monkeypatch.setattr("flask_limiter.Limiter", limiter_cls)

    return importlib.import_module(MODULE_NAME)


def test_config_loads_with_expected_constants(monkeypatch):
    config = _import_config(monkeypatch)

    assert config.IP_ADDRESS == "0.0.0.0"
    assert config.PORT_NUMBER == 10000
    assert config.REDIS_URL == "redis://localhost:6379/0"

    assert config.OPENAI_KEY == "test-key"
    assert config.OPENAI_ORG == "test-org"
    assert config.OPENAI_PROJECT == "test-project"
    assert config.OPENAI_MODEL == "test-model"

    assert config.POSTGRES_DB == "test-db"
    assert config.POSTGRES_USER == "test-user"
    assert config.POSTGRES_PASSWORD == "test-pass"
    assert config.POSTGRES_HOST == "test-host"
    assert config.POSTGRES_PORT == "5432"


def test_flask_app_uses_expected_static_and_template_paths(monkeypatch):
    config = _import_config(monkeypatch)

    assert config.flask_api is not None
    assert config.static_path.endswith(os.path.join("app", "static"))
    assert config.template_path.endswith(os.path.join("app", "templates"))
    assert config.flask_api.static_folder == config.static_path
    assert config.flask_api.template_folder == config.template_path


def test_redis_connection_is_created_and_pinged(monkeypatch):
    calls = {"url": None, "ping_called": False}

    class FakeRedisClient:
        def ping(self):
            calls["ping_called"] = True

    def fake_from_url(url):
        calls["url"] = url
        return FakeRedisClient()

    class FakeLimiter:
        def __init__(self, *args, **kwargs):
            pass

    _clear_config_module()
    _set_required_env(monkeypatch)
    monkeypatch.setattr("redis.from_url", fake_from_url)
    monkeypatch.setattr("flask_limiter.Limiter", FakeLimiter)

    importlib.import_module(MODULE_NAME)

    assert calls["url"] == "redis://localhost:6379/0"
    assert calls["ping_called"] is True


def test_limiter_is_configured_with_expected_values(monkeypatch):
    captured = {}

    class FakeLimiter:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    config = _import_config(monkeypatch, limiter_cls=FakeLimiter)

    assert captured["args"][0] is config.get_remote_address
    assert captured["kwargs"]["app"] is config.flask_api
    assert captured["kwargs"]["storage_uri"] == "redis://localhost:6379/0"
    assert captured["kwargs"]["default_limits"] == [
        "100 per day",
        "30 per hour",
        "2 per minute",
    ]


def test_import_raises_runtime_error_when_redis_is_unreachable(monkeypatch):
    class FailingRedisClient:
        def ping(self):
            raise redis.exceptions.ConnectionError("boom")

    class FakeLimiter:
        def __init__(self, *args, **kwargs):
            pass

    _clear_config_module()
    _set_required_env(monkeypatch)
    monkeypatch.setattr("redis.from_url", lambda url: FailingRedisClient())
    monkeypatch.setattr("flask_limiter.Limiter", FakeLimiter)

    with pytest.raises(RuntimeError, match="Failed to connect to Redis"):
        importlib.import_module(MODULE_NAME)
