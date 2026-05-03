"""Configuration for OpenAI-compatible LLM conversion."""

import os
from dataclasses import dataclass
from typing import Optional


class LLMConfigError(ValueError):
    """Raised when required LLM configuration is missing or invalid."""


@dataclass(frozen=True)
class LLMConfig:
    """Runtime configuration for an OpenAI-compatible chat API."""

    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 1.0
    timeout: float = 600.0
    max_tokens: int = 128000

    @classmethod
    def from_values(
        cls,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 1.0,
        timeout: float = 600.0,
        max_tokens: int = 128000,
    ) -> "LLMConfig":
        resolved_model = model or os.environ.get("LATEX_TOOLS_LLM_MODEL")
        resolved_api_key = api_key or os.environ.get("LATEX_TOOLS_LLM_API_KEY")
        resolved_base_url = base_url or os.environ.get("LATEX_TOOLS_LLM_BASE_URL")

        if not resolved_model:
            raise LLMConfigError(
                "Missing model. Set LATEX_TOOLS_LLM_MODEL or pass --model."
            )
        if not resolved_api_key:
            raise LLMConfigError(
                "Missing API key. Set LATEX_TOOLS_LLM_API_KEY or pass --api-key."
            )
        if temperature < 0:
            raise LLMConfigError("Temperature must be non-negative.")
        if timeout <= 0:
            raise LLMConfigError("Timeout must be positive.")
        if max_tokens <= 0:
            raise LLMConfigError("max_tokens must be positive.")

        return cls(
            model=resolved_model,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            temperature=temperature,
            timeout=timeout,
            max_tokens=max_tokens,
        )
