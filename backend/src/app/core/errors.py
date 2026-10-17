class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."


class AgentTimeout(AppError):
    """The agent did not finish within its time limit."""

    status_code = 504
    code = "AGENT_TIMEOUT"
    message = "The agent took too long. Please retry."


class AgentLimitReached(AppError):
    status_code = 422
    code = "AGENT_LIMIT_REACHED"
    message = "The agent could not finish within its step limit. Try a simpler question."


class EmptyAgentResponse(AppError):
    status_code = 502
    code = "EMPTY_AGENT_RESPONSE"
    message = "The model returned no answer. Please retry."


class RetrievalUnavailable(AppError):
    status_code = 503
    code = "RETRIEVAL_UNAVAILABLE"
    message = "The knowledge base is temporarily unavailable. Please retry."


class ModelUnavailable(AppError):
    status_code = 502
    code = "MODEL_UNAVAILABLE"
    message = "The model provider is temporarily unavailable. Please retry."
