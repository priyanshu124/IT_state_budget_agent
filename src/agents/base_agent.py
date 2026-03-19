"""Base class for TBM agents with shared run/token logging behavior."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger


class BaseAgent(ABC):
    """Shared base class for agent execution and token logging."""

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent workflow and emit a standard token usage summary."""
        result = self.execute(*args, **kwargs)
        self.log_token_usage()
        return result

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Run the core workflow for the agent."""

    def get_token_stats(self) -> dict[str, Any]:
        """Return token usage stats. Subclasses can override with real values."""
        return {
            "calls": [],
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

    def log_token_usage(self) -> None:
        """Emit a consistent token usage summary to the logger."""
        token_stats = self.get_token_stats() or {}
        calls = token_stats.get("calls", [])

        if not calls:
            logger.info("Token usage | no calls recorded")
            return

        for call in calls:
            logger.info(
                "Token usage | call={} model={} in={} out={} total={}",
                call.get("call_name", "unknown"),
                call.get("model", "unknown"),
                call.get("input_tokens", 0),
                call.get("output_tokens", 0),
                call.get("total_tokens", 0),
            )

        logger.info(
            "Token usage | total in={} out={} total={}",
            token_stats.get("total_input_tokens", 0),
            token_stats.get("total_output_tokens", 0),
            token_stats.get("total_tokens", 0),
        )
