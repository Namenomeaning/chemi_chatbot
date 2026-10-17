from pydantic import BaseModel, Field, model_validator


class QueryRequest(BaseModel):
    text: str | None = Field(default=None, max_length=12000)
    image_base64: str | None = Field(default=None, max_length=8_000_000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def require_input(self):
        if not (self.text and self.text.strip()) and not self.image_base64:
            raise ValueError("text or image required")
        return self


class Citation(BaseModel):
    id: str
    source: str


class QueryResponse(BaseModel):
    success: bool
    thread_id: str
    text_response: str | None = None
    image_base64: str | None = Field(default=None, description="Base64 or image URL")
    audio_base64: str | None = None
    quiz_data: dict | None = None
    error: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    abstained: bool = False
