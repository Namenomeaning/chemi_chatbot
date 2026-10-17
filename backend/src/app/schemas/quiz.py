import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MatchItem(BaseModel):
    left: str = Field(min_length=1, max_length=500)
    right_options: list[str] = Field(min_length=2, max_length=12)


class QuizData(BaseModel):
    """Validate the data contract consumed by the browser quiz controls."""

    quiz_id: str = Field(pattern=r"^[0-9a-f]{8}$")
    type: Literal["mcq", "matching", "free_text", "listening"]
    level: int = Field(ge=1, le=4)
    topic: str = Field(min_length=1, max_length=200)
    question_text: str = Field(min_length=1, max_length=8000)
    audio_script: str | None = None
    input_type: Literal["radio", "select", "text"]
    options: list[str] | None = None
    match_items: list[MatchItem] | None = None
    check_method: Literal["exact", "fuzzy"]
    correct_answer: str = Field(min_length=1, max_length=8000)
    accept_variants: list[str] | None = None
    explanation: str = Field(min_length=1, max_length=12000)

    @model_validator(mode="after")
    def validate_controls(self):
        expected = {"mcq": "radio", "listening": "radio", "matching": "select", "free_text": "text"}
        if self.input_type != expected[self.type]:
            raise ValueError("Quiz type and input control do not match")
        if self.input_type == "radio":
            if not self.options or not 2 <= len(self.options) <= 12:
                raise ValueError("A choice quiz requires 2 to 12 options")
            self.correct_answer = self.correct_answer.strip().upper()
            if self.correct_answer not in [chr(65 + index) for index in range(len(self.options))]:
                raise ValueError("The correct answer must be an option letter")
        if self.type == "listening" and not (self.audio_script and self.audio_script.strip()):
            raise ValueError("A listening quiz requires a script")
        if self.input_type == "select":
            if not self.match_items:
                raise ValueError("A matching quiz requires items")
            pairs = json.loads(self.correct_answer)
            if not isinstance(pairs, dict) or set(pairs) != {item.left for item in self.match_items}:
                raise ValueError("Matching answers must cover every item")
            if any(pairs[item.left] not in item.right_options for item in self.match_items):
                raise ValueError("Matching answers must be available options")
        return self
