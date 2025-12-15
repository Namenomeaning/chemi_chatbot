"""Simplified agent state - ReAct agent manages state internally."""

# Note: With create_react_agent, the state is managed automatically.
# This file is kept for backwards compatibility and potential future extensions.

from typing import Optional, Dict, Any

# Response type for API/UI consumption
class ChatResponse:
    """Response from the chemistry chatbot.

    Attributes:
        text: The text response from the agent
        image_url: Optional URL/path to compound structure image
        audio_url: Optional URL/path to pronunciation audio
    """

    def __init__(
        self,
        text: str,
        image_url: Optional[str] = None,
        audio_url: Optional[str] = None,
    ):
        self.text = text
        self.image_url = image_url
        self.audio_url = audio_url

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "image_url": self.image_url,
            "audio_url": self.audio_url,
        }
