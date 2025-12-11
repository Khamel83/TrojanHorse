"""LLM client for OpenRouter API integration."""

import json
import time
import logging
from typing import List, Dict, Optional, Any
import requests

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMClient:
    """Client for interacting with OpenRouter API."""

    def __init__(self, api_key: str, model: str = "google/gemini-2.5-flash-lite-001"):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Khamel83/TrojanHorse",
            "X-Title": "TrojanHorse Note Processor",
        })

    def call_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Call OpenRouter chat completion API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override model (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_retries: Maximum retry attempts

        Returns:
            Generated text response

        Raises:
            LLMClientError: If API call fails after retries
        """
        model = model or self.model

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"LLM request attempt {attempt + 1}/{max_retries + 1}")

                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()

                data = response.json()

                # Extract the response text
                if "choices" not in data or not data["choices"]:
                    raise LLMClientError("Invalid response format: no choices found")

                choice = data["choices"][0]
                if "message" not in choice or "content" not in choice["message"]:
                    raise LLMClientError("Invalid response format: no message content found")

                content = choice["message"]["content"]
                logger.debug(f"LLM response received, length: {len(content)}")
                return content

            except requests.exceptions.RequestException as e:
                logger.warning(f"LLM API request failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise LLMClientError(f"API request failed after {max_retries + 1} attempts: {e}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response JSON: {e}")
                if attempt == max_retries:
                    raise LLMClientError(f"Invalid JSON response after {max_retries + 1} attempts: {e}")

            except KeyError as e:
                logger.error(f"Missing expected field in LLM response: {e}")
                if attempt == max_retries:
                    raise LLMClientError(f"Malformed response after {max_retries + 1} attempts: {e}")

            except Exception as e:
                logger.error(f"Unexpected error in LLM request (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise LLMClientError(f"Unexpected error after {max_retries + 1} attempts: {e}")

            # Exponential backoff before retry
            if attempt < max_retries:
                sleep_time = 2 ** attempt
                logger.debug(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        # This should never be reached
        raise LLMClientError("Unexpected error in call_chat")

    def call_structured(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Call LLM and parse response as JSON.

        This method is useful for structured outputs like classification results.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override model (optional)
            max_retries: Maximum retry attempts

        Returns:
            Parsed JSON response as dict

        Raises:
            LLMClientError: If API call fails or JSON parsing fails
        """
        # Add a system message asking for JSON output if not present
        has_json_instruction = any(
            "json" in msg.get("content", "").lower()
            for msg in messages
            if msg.get("role") == "system"
        )

        if not has_json_instruction:
            messages.insert(0, {
                "role": "system",
                "content": "Respond with valid JSON only. No additional text or explanations."
            })

        response_text = self.call_chat(
            messages=messages,
            model=model,
            temperature=0.1,  # Lower temperature for structured outputs
            max_retries=max_retries,
        )

        # Try to parse as JSON
        try:
            # Clean up the response - remove any markdown code blocks
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            raise LLMClientError(f"Failed to parse response as JSON: {e}")

    def test_connection(self) -> bool:
        """
        Test if the API connection is working.

        Returns:
            True if connection is successful
        """
        try:
            response = self.call_chat([
                {"role": "user", "content": "Respond with just the word 'OK'"}
            ])
            return response.strip().lower() == "ok"
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False