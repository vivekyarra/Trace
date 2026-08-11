"""
Claude API client wrapper for LORE. All Claude calls go through this module.
"""

import logging
from pathlib import Path

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    CLAUDE_TEMPERATURE,
)

logger = logging.getLogger("lore.claude_client")


class ClaudeClient:
    """
    Wraps the Anthropic SDK for Claude. Uses config defaults; call() allows overrides.
    """

    def __init__(self) -> None:
        """
        Initialise Anthropic client using ANTHROPIC_API_KEY from config.
        """
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Call Claude with the given system and user messages. Uses CLAUDE_MODEL,
        CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE from config as defaults; overrides
        if passed. Returns the assistant text response as a plain string.
        """
        tokens = max_tokens if max_tokens is not None else CLAUDE_MAX_TOKENS
        temp = temperature if temperature is not None else CLAUDE_TEMPERATURE
        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temp,
            )
            if not response.content:
                return ""
            first = response.content[0]
            if hasattr(first, "text"):
                return first.text
            return str(first)
        except anthropic.APIError as e:
            logger.exception("Claude API error")
            raise RuntimeError(f"Claude API call failed: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error calling Claude")
            raise RuntimeError(f"Claude API call failed: {e}") from e

    def load_prompt(self, prompt_name: str) -> str:
        """
        Read and return the content of prompts/{prompt_name}.txt. Raises
        FileNotFoundError with a clear message if the file does not exist.
        """
        path = Path(__file__).resolve().parent.parent / "prompts" / f"{prompt_name}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")
