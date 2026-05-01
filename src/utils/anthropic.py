"""Anthropic client initialization helpers."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src.utils.config import ANTHROPIC_API_KEY
from src.utils.config import get_anthropic_call_config


class AnthropicClient:
    """Class-based Anthropic client initializer and holder."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._client = None
        self.token_stats = {
            "calls": [],
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

    def _validate_key(self) -> None:
        if not self.api_key or self.api_key.startswith("sk-ant-your"):
            raise ValueError("ANTHROPIC_API_KEY is not configured")

    def get_client(self):
        """Lazily create and return an Anthropic SDK client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ImportError("Install anthropic: pip install anthropic") from e

            self._validate_key()
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _record_usage(self, call_name: str, model: str, usage) -> None:
        """Record token usage for one LLM call and update totals."""
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = input_tokens + output_tokens

        self.token_stats["calls"].append(
            {
                "call_name": call_name,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
        )
        self.token_stats["total_input_tokens"] += input_tokens
        self.token_stats["total_output_tokens"] += output_tokens
        self.token_stats["total_tokens"] += total_tokens

    def llm_call(self, call_name: str, system: str, messages: list[dict]):
        """Execute one Anthropic call using per-call config from llm.yaml."""
        call_cfg = get_anthropic_call_config(call_name)
        model = call_cfg["model"]
        max_tokens = int(call_cfg["max_tokens"])

        response = self.get_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

        usage = response.usage
        self._record_usage(call_name, model, usage)
        logger.info(
            f"{call_name} | model={model} | "
            f"tokens in={usage.input_tokens} out={usage.output_tokens} "
            f"total={usage.input_tokens + usage.output_tokens}"
        )

        return response

    def get_token_stats(self) -> dict:
        """Return accumulated token usage stats for this client instance."""
        return self.token_stats


def init_anthropic_client(api_key: Optional[str] = None):
    """Backward-compatible helper that returns an initialized Anthropic client."""
    return AnthropicClient(api_key=api_key).get_client()


