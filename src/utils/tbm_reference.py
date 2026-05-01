from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path


def resolve_reference_path(path: str | Path) -> Path:
    """Resolve a TBM reference path with a small compatibility fallback.

    Supports the raw CSV reference files the project now uses, and tolerates the
    singular/plural tower filename mismatch (`it_tower.csv` vs `it_towers.csv`).
    """

    candidate = Path(path)
    if candidate.exists():
        return candidate

    if candidate.name == "it_tower.csv":
        plural = candidate.with_name("it_towers.csv")
        if plural.exists():
            return plural

    if candidate.name == "it_towers.csv":
        singular = candidate.with_name("it_tower.csv")
        if singular.exists():
            return singular

    return candidate


def _clean_text(value: str | None) -> str:
    return str(value or "").strip()


def build_cost_pool_reference_text(csv_path: str | Path) -> str:
    """Build compact prompt text from raw cost_pools.csv (names only)."""

    path = resolve_reference_path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    pools: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
    for row in rows:
        pool = _clean_text(row.get("Cost Pool"))
        sub_pool = _clean_text(row.get("Cost Sub-Pool"))

        if not pool or not sub_pool:
            continue
        if pool.upper() == "RETIRED" or sub_pool.upper() == "RETIRED":
            continue

        sub_pools = pools.setdefault(pool, OrderedDict())
        if sub_pool not in sub_pools:
            sub_pools[sub_pool] = None

    lines: list[str] = []
    for pool, sub_pools in pools.items():
        lines.append(f"[{pool}]")
        for sub_pool in sub_pools.keys():
            lines.append(f"  - {sub_pool}")

    return "\n".join(lines)


def build_tower_reference_text(csv_path: str | Path) -> str:
    """Build compact prompt text from raw it_towers.csv (names only)."""

    path = resolve_reference_path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    towers: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
    for row in rows:
        tower = _clean_text(row.get("Tower"))
        sub_tower = _clean_text(row.get("Sub-Tower"))

        if not tower or not sub_tower:
            continue
        if tower.upper() == "RETIRED" or sub_tower.upper() == "RETIRED":
            continue

        sub_towers = towers.setdefault(tower, OrderedDict())
        if sub_tower not in sub_towers:
            sub_towers[sub_tower] = None

    lines: list[str] = []
    for tower, sub_towers in towers.items():
        lines.append(f"[{tower}]")
        for sub_tower in sub_towers.keys():
            lines.append(f"  - {sub_tower}")

    return "\n".join(lines)