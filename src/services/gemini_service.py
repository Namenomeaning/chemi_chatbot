"""Gemini API client helper."""

import os
import json
from typing import Optional, Dict, Any, Type, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

from ..core.logging import setup_logging

T = TypeVar('T', bound=BaseModel)

load_dotenv(override=True)
logger = setup_logging(__name__)


class GeminiService:
    """Service class for Gemini API interactions."""

    def __init__(self):
        """Initialize Gemini client."""
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_GEMINI_API_KEY environment variable not set")

        self.client = genai.Client(api_key=api_key)
        self.model_name = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash-lite")

        # Cost optimization defaults
        self.max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1024"))
        self.top_p = float(os.getenv("GEMINI_TOP_P", "0.95"))

    def generate_json(
        self,
        prompt: str,
        image: Optional[bytes] = None,
        temperature: float = 0.1,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON response from Gemini.

        Args:
            prompt: Text prompt for the model
            image: Optional image bytes for multimodal input
            temperature: Sampling temperature (0.0-1.0)
            model: Optional model override (default: from env GEMINI_LLM_MODEL)

        Returns:
            Parsed JSON response as dictionary
        """
        model_name = model or self.model_name
        # Prepare content
        if image:
            # Multimodal: text + image
            content = [
                types.Part(text=prompt),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",  # Use PNG for molecular structure images
                        data=image
                    )
                )
            ]
        else:
            # Text only
            content = prompt

        # Generate response
        response = self.client.models.generate_content(
            model=model_name,
            contents=content,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json"
            )
        )

        # Parse JSON
        try:
            result = json.loads(response.text)
            return result
        except json.JSONDecodeError as e:
            # Fallback: return raw text in error field
            return {"error": f"JSON parse error: {e}", "raw_text": response.text}

    def generate_text(
        self,
        prompt: str,
        image: Optional[bytes] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate text response from Gemini.

        Args:
            prompt: Text prompt for the model
            image: Optional image bytes for multimodal input
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text response
        """
        # Prepare content
        if image:
            content = [
                types.Part(text=prompt),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",  # Use PNG for molecular structure images
                        data=image
                    )
                )
            ]
        else:
            content = prompt

        # Generate response
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=content,
            config=types.GenerateContentConfig(temperature=temperature)
        )

        return response.text

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        image: Optional[bytes] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        top_p: Optional[float] = None
    ) -> T:
        """Generate structured response using Pydantic schema.

        Args:
            prompt: Text prompt for the model
            response_schema: Pydantic BaseModel class for response structure
            image: Optional image bytes for multimodal input
            temperature: Sampling temperature (0.0-1.0)
            model: Optional model override
            max_output_tokens: Maximum tokens (default from env/1024)
            top_p: Nucleus sampling (default from env/0.95)

        Returns:
            Instantiated Pydantic model with parsed response
        """
        model_name = model or self.model_name

        # Prepare content
        if image:
            content = [
                types.Part(text=prompt),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",  # Use PNG for molecular structure images
                        data=image
                    )
                )
            ]
        else:
            content = prompt

        # Build config with defaults
        config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "max_output_tokens": max_output_tokens or self.max_output_tokens,
            "top_p": top_p or self.top_p
        }

        # Generate response with structured output
        try:
            logger.debug(f"Gemini API call - model: {model_name}, schema: {response_schema.__name__}")
            response = self.client.models.generate_content(
                model=model_name,
                contents=content,
                config=config
            )
            return response.parsed
        except Exception as e:
            logger.error(f"Gemini API error - model: {model_name}, schema: {response_schema.__name__}, error: {str(e)}", exc_info=True)
            raise


# Global instance
gemini_service = GeminiService()
