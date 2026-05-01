"""Helpers for resolving raw input files and folders."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".parquet"}


def resolve_input_path(filepath: str | Path) -> Path:
    """Resolve a raw input path to a concrete file.

    Accepts either a file path or a folder containing one or more raw files.
    When a folder is provided, the newest supported file is selected.
    """

    path = Path(filepath)
    if path.is_file():
        return path

    if path.is_dir():
        candidates = [
            candidate
            for candidate in path.iterdir()
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_DATA_SUFFIXES
        ]
        if not candidates:
            raise FileNotFoundError(f"No supported raw data files found in: {path}")
        return max(candidates, key=lambda candidate: (candidate.stat().st_mtime, candidate.name))

    raise FileNotFoundError(f"Data file or folder not found: {path}")