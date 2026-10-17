import logging

from pydantic import ValidationError

from app.schemas.quiz import QuizData

logger = logging.getLogger(__name__)


def parse_quiz(data: dict | None) -> dict | None:
    if not data:
        return None
    try:
        return QuizData.model_validate(data).model_dump()
    except ValidationError:
        logger.warning("invalid_quiz_artifact")
        return None
