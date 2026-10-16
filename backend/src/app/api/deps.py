from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.core.config import Settings, load_settings
from app.services.cloudflare import to_js_obj

_settings: Settings | None = None


def get_env(request: Request):
    return request.scope["env"]


def get_settings(request: Request) -> Settings:
    """Build Settings on the first request. The env does not exist at import time."""
    global _settings
    if _settings is None:
        try:
            _settings = load_settings(get_env(request))
        except ValidationError as e:
            # Name the fields only. Never echo values.
            fields = ", ".join(str(err["loc"][0]).upper() for err in e.errors())
            raise HTTPException(503, f"Server is not configured. Missing or invalid: {fields}") from e
    return _settings


async def check_rate_limit(request: Request) -> None:
    """Allow 10 requests per 60 s per client IP (limit is set in wrangler.jsonc)."""
    key = request.headers.get("cf-connecting-ip") or "local"
    result = await get_env(request).LIMITER.limit(to_js_obj({"key": key}))
    if not result.success:
        raise HTTPException(429, "Quá nhiều yêu cầu, vui lòng thử lại sau ít phút")
