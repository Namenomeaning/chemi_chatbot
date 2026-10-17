from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fakes import FakeD1, FakeLimiter, FakeR2


@pytest.fixture(autouse=True)
def python_binding_values(monkeypatch):
    # CPython fakes use Python values. Only the Worker runtime needs JS conversion.
    monkeypatch.setattr("app.api.deps.to_js_obj", lambda value: value)
    monkeypatch.setattr("app.services.retrieval.to_js_obj", lambda value: value)
    monkeypatch.setattr("app.tools.factory.to_js_bytes", lambda value: value)


@pytest.fixture
def env():
    return SimpleNamespace(
        DB=FakeD1(),
        ARTIFACTS=FakeR2(),
        LIMITER=FakeLimiter(),
        OPENROUTER_API_KEY="fake-model-key",
        API_KEYS="test-access-key",
        APP_ENV="test",
    )


@pytest.fixture
def client(env):
    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    with TestClient(with_env, raise_server_exceptions=False) as client:
        yield client
