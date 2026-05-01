from __future__ import annotations

from typing import Any

import yaml

from src.utils.config import get_config


def normalize_it_programs_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Normalize config into a shape with top-level it_programs."""
    if not isinstance(raw_config, dict):
        return {}

    if isinstance(raw_config.get("it_programs"), dict):
        return raw_config

    if "fields" in raw_config or "designations" in raw_config:
        return {
            "it_programs": {
                "fields": raw_config.get("fields", {}),
                "designations": raw_config.get("designations", []),
            }
        }

    return raw_config


def load_runtime_config(config_path: str | None) -> dict[str, Any]:
    """Load designation config from file or merged project config."""
    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
    else:
        raw_config = get_config()

    config = normalize_it_programs_config(raw_config)
    designations = config.get("it_programs", {}).get("designations", [])
    if not designations:
        raise ValueError(
            "Missing it_programs.designations in config. "
            "Provide --config configs/it_programs.yaml or define it_programs in merged configs."
        )

    return config
