"""
Configuration loader for TBM Classification Engine.
Loads YAML configs + .env variables into a single accessible object.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger


# Project root = two levels up from this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"


def load_env() -> None:
    """Load .env file from project root."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env from {env_path}")
    else:
        logger.warning(f"No .env found at {env_path} — using system env vars")


def load_yaml_config(filename: str = "tbm_config.yaml") -> dict[str, Any]:
    """Load the main YAML configuration file."""
    config_path = CONFIG_DIR / filename
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded config from {config_path}")
    return config


def load_all_yaml_configs() -> dict[str, dict[str, Any]]:
    """Load all YAML files under configs/ into a name -> config mapping."""
    configs: dict[str, dict[str, Any]] = {}
    for config_path in sorted(CONFIG_DIR.glob("*.yaml")):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        configs[config_path.stem] = data
        logger.info(f"Loaded config from {config_path}")
    return configs


def _deep_merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base and return a new dict."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _bootstrap_config_state() -> dict[str, Any]:
    """Load env/config and build module-level config state."""
    load_env()
    configs = load_all_yaml_configs()

    merged: dict[str, Any] = {}
    for cfg in configs.values():
        if isinstance(cfg, dict):
            merged = _deep_merge_dicts(merged, cfg)

    anthropic_cfg = merged.get("anthropic", {}) if isinstance(merged, dict) else {}
    anthropic_default_cfg = anthropic_cfg.get("default", {}) if isinstance(anthropic_cfg, dict) else {}

    return {
        "configs": configs,
        "config": merged,
        "tbm_config": configs.get("tbm", {}),
        "llm_config": configs.get("llm", {}),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "claude_model": anthropic_default_cfg.get(
            "model",
            os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        ),
        "claude_max_tokens": int(anthropic_default_cfg.get("max_tokens", 8192)),
    }


_STATE = _bootstrap_config_state()

# Public module-level config objects
CONFIGS: dict[str, dict[str, Any]] = _STATE["configs"]
CONFIG: dict[str, Any] = _STATE["config"]
TBM_CONFIG: dict[str, Any] = _STATE["tbm_config"]
LLM_CONFIG: dict[str, Any] = _STATE["llm_config"]

# Public module-level runtime/env values
ANTHROPIC_API_KEY: str = _STATE["anthropic_api_key"]
CLAUDE_MODEL: str = _STATE["claude_model"]
CLAUDE_MAX_TOKENS: int = _STATE["claude_max_tokens"]

# Convenience values commonly used by pipeline code
PIPELINE_CONFIG: dict[str, Any] = CONFIG.get("pipeline", {})
BATCH_SIZE: int = PIPELINE_CONFIG.get("batch_size", 50)
MAX_RETRIES: int = PIPELINE_CONFIG.get("max_retries", 3)
CONFIDENCE_THRESHOLD: float = PIPELINE_CONFIG.get("confidence_threshold", 0.7)

COST_POOL_MAPPINGS: dict[str, str] = CONFIG.get("cost_pool_mappings", {})
IT_TOWERS: list[str] = CONFIG.get("it_towers", [])
KNOWN_IT_AGENCIES: list[dict] = CONFIG.get("known_it_agencies", [])
SHADOW_IT_KEYWORDS: dict[str, list[str]] = CONFIG.get("shadow_it_keywords", {})
AGENT_ROUTING: dict[str, dict] = CONFIG.get("agent_routing", {})
IT_PROGRAMS_CONFIG: dict[str, Any] = CONFIG.get("it_programs", {})

DATA_RAW = DATA_DIR / "raw"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_OUTPUT = DATA_DIR / "output"
TBM_COST_POOLS_CSV = DATA_RAW / "tbm" / "cost_pools.csv"
TBM_IT_TOWERS_CSV = DATA_RAW / "tbm" / "it_towers.csv"


def known_it_agency_codes() -> set[str]:
    """Quick lookup set of agency codes that are known IT."""
    return {a["agency_code"] for a in KNOWN_IT_AGENCIES}


def validate() -> bool:
    """Check that critical settings are present."""
    issues = []
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("sk-ant-your"):
        issues.append("ANTHROPIC_API_KEY not set")
    if not TBM_COST_POOLS_CSV.exists():
        issues.append(f"Missing TBM cost pool reference CSV: {TBM_COST_POOLS_CSV}")
    if not TBM_IT_TOWERS_CSV.exists():
        issues.append(f"Missing TBM tower reference CSV: {TBM_IT_TOWERS_CSV}")

    if issues:
        for issue in issues:
            logger.warning(f"Config issue: {issue}")
        return False

    logger.info("Configuration validated successfully")
    return True


def get_config() -> dict[str, Any]:
    """Compatibility helper returning merged config mapping."""
    return CONFIG


def get_anthropic_call_config(call_name: str) -> dict[str, Any]:
    """Return Anthropic config for a specific call type, merged with defaults."""
    anthropic_cfg = CONFIG.get("anthropic", {}) if isinstance(CONFIG, dict) else {}
    default_cfg = anthropic_cfg.get("default", {}) if isinstance(anthropic_cfg, dict) else {}
    calls_cfg = anthropic_cfg.get("calls", {}) if isinstance(anthropic_cfg, dict) else {}
    call_cfg = calls_cfg.get(call_name, {}) if isinstance(calls_cfg, dict) else {}

    resolved_model = call_cfg.get("model", default_cfg.get("model", CLAUDE_MODEL))
    resolved_max_tokens = int(
        call_cfg.get("max_tokens", default_cfg.get("max_tokens", CLAUDE_MAX_TOKENS))
    )

    return {
        "model": resolved_model,
        "max_tokens": resolved_max_tokens,
    }
