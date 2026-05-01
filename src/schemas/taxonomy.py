"""
Pydantic models for TBM Taxonomy structure.

These models define the schema for the extracted taxonomy config.
Agent 1 (Taxonomy Extractor) produces output validated against these models.
All downstream agents and classifiers reference the YAML generated from these.
"""

from pydantic import BaseModel, Field
from typing import Optional


class CostSubPool(BaseModel):
    """A single sub-pool within a cost pool."""

    name: str = Field(description="Sub-pool name, e.g. 'Internal Labor', 'Licensing'")
    description: str = Field(description="Definition from TBM taxonomy")


class CostPool(BaseModel):
    """A single TBM cost pool with its sub-pools."""

    name: str = Field(description="Cost pool name, e.g. 'Staffing', 'Software & SaaS'")
    description: str = Field(description="High-level definition of this cost pool")
    opex_sub_pools: list[CostSubPool] = Field(
        default_factory=list,
        description="Operating expense sub-pools"
    )
    capex_sub_pools: list[CostSubPool] = Field(
        default_factory=list,
        description="Capital expense sub-pools"
    )


class TBMTaxonomyCostPools(BaseModel):
    """Complete extracted cost pool layer from a TBM taxonomy document."""

    tbm_version: str = Field(description="Taxonomy version, e.g. '5.0.1'")
    source_document: str = Field(description="Filename of the source PDF")
    cost_pools: list[CostPool] = Field(description="All extracted cost pools")

    def get_cost_pool_names(self) -> list[str]:
        """Return flat list of all cost pool names."""
        return [cp.name for cp in self.cost_pools]

    def get_all_sub_pool_names(self) -> list[str]:
        """Return flat list of all sub-pool names (opex + capex)."""
        names = []
        for cp in self.cost_pools:
            for sp in cp.opex_sub_pools:
                names.append(f"{cp.name} / {sp.name}")
            for sp in cp.capex_sub_pools:
                names.append(f"{cp.name} / {sp.name}")
        return names

    def to_yaml_dict(self) -> dict:
        """Convert to a clean dict suitable for YAML serialization."""
        return {
            "metadata": {
                "tbm_version": self.tbm_version,
                "source_document": self.source_document,
            },
            "cost_pools": [
                {
                    "name": cp.name,
                    "description": cp.description,
                    "opex_sub_pools": [
                        {"name": sp.name, "description": sp.description}
                        for sp in cp.opex_sub_pools
                    ],
                    "capex_sub_pools": [
                        {"name": sp.name, "description": sp.description}
                        for sp in cp.capex_sub_pools
                    ],
                }
                for cp in self.cost_pools
            ],
        }
# ── Resource Tower Layer ───────────────────────────────────────

class SubTower(BaseModel):
    """A single sub-tower within a tower."""
    name: str = Field(description="Sub-tower name, e.g. 'Servers', 'LAN', 'Development'")
    description: str = Field(description="Definition from TBM taxonomy")


class Tower(BaseModel):
    """A single TBM resource tower with its sub-towers."""
    name: str = Field(description="Tower name, e.g. 'Compute', 'Application', 'Security'")
    domain: str = Field(description="Parent domain: Infrastructure, Application, Operations, or Field & Office")
    description: str = Field(description="High-level definition of this tower")
    sub_towers: list[SubTower] = Field(default_factory=list)


class TBMTaxonomyTowers(BaseModel):
    """Complete extracted resource tower layer from a TBM taxonomy document."""
    tbm_version: str = Field(description="Taxonomy version, e.g. '5.0.1'")
    source_document: str = Field(description="Filename of the source PDF")
    towers: list[Tower] = Field(description="All extracted towers")

    def get_tower_names(self) -> list[str]:
        return [t.name for t in self.towers]

    def get_all_sub_tower_names(self) -> list[str]:
        names = []
        for t in self.towers:
            for st in t.sub_towers:
                names.append(f"{t.name} / {st.name}")
        return names

    def get_towers_by_domain(self) -> dict[str, list[str]]:
        domains: dict[str, list[str]] = {}
        for t in self.towers:
            domains.setdefault(t.domain, []).append(t.name)
        return domains

    def to_yaml_dict(self) -> dict:
        return {
            "metadata": {
                "tbm_version": self.tbm_version,
                "source_document": self.source_document,
            },
            "towers": [
                {
                    "name": t.name,
                    "domain": t.domain,
                    "description": t.description,
                    "sub_towers": [
                        {"name": st.name, "description": st.description}
                        for st in t.sub_towers
                    ],
                }
                for t in self.towers
            ],
        }