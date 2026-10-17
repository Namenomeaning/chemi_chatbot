import hashlib
import secrets

from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError

from app.core.config import load_settings
from app.services.cloudflare import to_js_obj


def get_env(request: Request):
    return request.scope["env"]


def get_settings(request: Request):
    # Cache on this request only. Tests and different bindings cannot share stale secrets.
    if not hasattr(request.state, "settings"):
        try:
            request.state.settings = load_settings(get_env(request))
        except ValidationError as exc:
            raise HTTPException(503, "Server configuration is incomplete or invalid.") from exc
    return request.state.settings


async def require_api_key(request: Request, settings=Depends(get_settings)) -> str:
    supplied = request.headers.get("x-api-key", "")
    if settings.api_keys:
        valid = any(
            secrets.compare_digest(supplied.encode(), key.get_secret_value().encode()) for key in settings.api_keys
        )
        if not valid:
            raise HTTPException(401, "A valid X-API-Key is required.")
        return hashlib.sha256(supplied.encode()).hexdigest()
    return "local"


async def check_rate_limit(request: Request, principal=Depends(require_api_key)) -> str:
    identity = principal if principal != "local" else request.headers.get("cf-connecting-ip", "local")
    key = hashlib.sha256(identity.encode()).hexdigest()
    result = await get_env(request).LIMITER.limit(to_js_obj({"key": key}))
    if not result.success:
        raise HTTPException(429, "Too many requests. Please retry later.", headers={"Retry-After": "60"})
    return principal
