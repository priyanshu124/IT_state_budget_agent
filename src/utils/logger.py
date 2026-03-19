"""
Logging configuration for TBM Classification Engine.
Uses loguru for structured, readable logs.
"""

import sys
from pathlib import Path

from loguru import logger

from src.utils.config import PROJECT_ROOT


def setup_logger(level: str = "INFO") -> None:
    """
    Configure loguru for the project.

    Outputs to:
    - Console (colorized, concise)
    - File (detailed, rotated daily)
    """
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console: concise format
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File: detailed format, rotated daily
    logger.add(
        log_dir / "tbm_pipeline_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="30 days",
        compression="zip",
    )

    logger.info(f"Logger initialized at level={level}")
