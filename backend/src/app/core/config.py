from typing import Any, Literal

from pydantic import BaseModel, SecretStr


class Settings(BaseModel):
    app_env: Literal["local", "production"] = "local"
    openai_api_key: SecretStr
    openai_base_url: str = "https://gpt3.shupremium.com/v1"
    openai_model: str = "gpt-4.1-mini"
    groq_api_key: SecretStr
    serpapi_key: SecretStr | None = None


def load_settings(env: Any) -> Settings:
    """Build Settings from the Worker env. os.environ does not hold Worker secrets."""
    values = {}
    for name in Settings.model_fields:
        value = getattr(env, name.upper(), None)
        if value is not None:
            values[name] = value
    return Settings.model_validate(values)
