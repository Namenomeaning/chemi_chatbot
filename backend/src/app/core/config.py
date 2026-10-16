from typing import Any, Literal

from pydantic import BaseModel, SecretStr


class Settings(BaseModel):
    app_env: Literal["local", "production"] = "local"
    openrouter_api_key: SecretStr
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-6-luna"
    quiz_model: str = "openai/gpt-oss-120b"
    tts_model: str = "hexgrad/kokoro-82m"
    tts_voice: str = "af_heart"
    serpapi_key: SecretStr | None = None


def load_settings(env: Any) -> Settings:
    """Build Settings from the Worker env. os.environ does not hold Worker secrets."""
    values = {}
    for name in Settings.model_fields:
        value = getattr(env, name.upper(), None)
        if value not in (None, ""):  # an empty value counts as not set
            values[name] = value
    return Settings.model_validate(values)
