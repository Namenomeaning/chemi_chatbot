import json
import time
import uuid

from starlette.middleware.cors import CORSMiddleware

from app.core.config import DEFAULT_ORIGINS


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()
        status = 500

        async def send_response(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = {
                    **message,
                    "headers": [
                        *(header for header in message.get("headers", []) if header[0].lower() != b"x-request-id"),
                        (b"x-request-id", request_id.encode()),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            print(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    }
                )
            )


class WorkerCORSMiddleware:
    """Origins come from Worker bindings, which exist only during requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        env = scope.get("env")
        configured = getattr(env, "CORS_ORIGINS", "") if env is not None else ""
        origins = [s.strip() for s in configured.split(",") if s.strip()] if configured else DEFAULT_ORIGINS
        cors = CORSMiddleware(
            self.app,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
            expose_headers=["X-Request-ID"],
        )
        await cors(scope, receive, send)
