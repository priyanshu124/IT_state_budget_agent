"""
Logging configuration for TBM Classification Engine.
Uses loguru for structured, readable logs.
"""

import os
import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path | None = None, level: str | None = None) -> None:
    """
    Configure loguru logging.

    Args:
        log_dir: Directory for log files. Defaults to project logs/ dir.
        level: Log level. Defaults to LOG_LEVEL env var or INFO.
    """
    # Remove default handler
    logger.remove()

    level = level or os.getenv("LOG_LEVEL", "INFO")

    # Console handler - concise format
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # File handler - detailed format
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "tbm_pipeline_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="gz",
    )

    logger.info(f"Logging initialized at level={level}")
