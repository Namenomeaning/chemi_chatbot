from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

DEFAULT_ORIGINS = ["https://chemi.quangiz.me", "http://localhost:8787", "http://127.0.0.1:8787"]


class Settings(BaseModel):
    app_env: Literal["local", "test", "production"] = "local"
    openrouter_api_key: SecretStr
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-6-luna"
    quiz_model: str = "openai/gpt-oss-120b"
    tts_model: str = "hexgrad/kokoro-82m"
    tts_voice: str = "af_heart"
    serpapi_key: SecretStr | None = None
    api_keys: list[SecretStr] = Field(default_factory=list)
    cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_ORIGINS))
    rag_enabled: bool = False
    embedding_model: str = "@cf/baai/bge-base-en-v1.5"
    retrieval_min_score: float = Field(default=0.65, ge=0, le=1)
    retrieval_top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("api_keys", "cors_origins", mode="before")
    @classmethod
    def split_values(cls, value):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def require_production_keys(self):
        if self.app_env == "production" and not self.api_keys:
            raise ValueError("Production requires API_KEYS")
        return self


def load_settings(env: Any) -> Settings:
    """Read Worker bindings on a request, never at module import time."""
    values = {}
    for name in Settings.model_fields:
        value = getattr(env, name.upper(), None)
        if value not in (None, ""):
            values[name] = value
    return Settings.model_validate(values)
