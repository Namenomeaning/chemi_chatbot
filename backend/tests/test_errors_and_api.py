import pytest

from app.core.errors import AgentLimitReached, AgentTimeout

HEADERS = {"X-API-Key": "test-access-key"}


def test_health_and_ready_without_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_missing_and_invalid_api_key(client):
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = client.post("/query", json={"text": "hello"}, headers=headers)
        assert response.status_code == 401
        assert response.json()["error_code"] == "HTTP_401"


@pytest.mark.parametrize(
    "payload", [{}, {"text": "  "}, {"text": "hello", "thread_id": "../other"}, {"text": "x" * 12001}]
)
def test_invalid_request(client, payload):
    response = client.post("/query", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert "input" not in response.text


@pytest.mark.parametrize(
    "error,status,code",
    [
        (AgentTimeout(), 504, "AGENT_TIMEOUT"),
        (AgentLimitReached(), 422, "AGENT_LIMIT_REACHED"),
        (RuntimeError("secret-provider-url"), 500, "INTERNAL_ERROR"),
    ],
)
def test_shared_error_handlers(client, monkeypatch, error, status, code):
    async def fail(*args):
        raise error

    monkeypatch.setattr("app.api.routes.query.answer_query", fail)
    response = client.post("/query", json={"text": "hello"}, headers=HEADERS)
    assert response.status_code == status
    assert response.json()["error_code"] == code
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert "secret-provider-url" not in response.text


def test_rate_limit(client, monkeypatch):
    async def fail(*args):
        raise AgentTimeout()

    monkeypatch.setattr("app.api.routes.query.answer_query", fail)
    for _ in range(10):
        assert client.post("/query", json={"text": "hello"}, headers=HEADERS).status_code == 504
    response = client.post("/query", json={"text": "hello"}, headers=HEADERS)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_cors_and_request_id(client, capsys):
    response = client.options(
        "/query",
        headers={
            "Origin": "https://chemi.quangiz.me",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://chemi.quangiz.me"
    assert response.headers["x-request-id"]
    rejected = client.options(
        "/query", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"}
    )
    assert rejected.status_code == 400
    output = capsys.readouterr().out
    assert '"event": "http_request"' in output
    assert "test-access-key" not in output


def test_production_requires_configured_access_keys(client, env):
    env.APP_ENV = "production"
    env.API_KEYS = ""
    assert client.post("/query", json={"text": "hello"}).status_code == 503
