"""
MFR Data Models
================
Structured models for Maryland MFR data extraction.
Designed to support Zero-Based Budgeting decision packages.

Key design decisions:
1. priority_number (1-10) maps to Moore-Miller State Plan priorities
2. kpi_number (e.g. "1.6") is the exact KPI reference from the MFR report
3. responsible_agency + data_source_agency distinguish who owns vs who reports
4. report_years (not fiscal_years) per MFR normalization convention
5. favorability_criteria stored so ZBB agent knows what "good" means for each measure
6. source_doc + source_page preserved for citations
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MeasureStatus(str, Enum):
    STRONGLY_FAVORABLE = "strongly_favorable"
    FAVORABLE = "favorable"
    STABLE = "stable"
    UNFAVORABLE = "unfavorable"
    STRONGLY_UNFAVORABLE = "strongly_unfavorable"
    VARIABLE = "variable"  # measures with both favorable/unfavorable aspects
    NA = "n/a"


class TrendDirection(str, Enum):
    HIGHER_IS_FAVORABLE = "higher_is_favorable"
    LOWER_IS_FAVORABLE = "lower_is_favorable"
    VARIABLE = "variable"


class MeasureType(str, Enum):
    OUTPUT = "output"       # What the program produces (units served, cases processed)
    OUTCOME = "outcome"     # The result achieved (graduation rate, crime rate)
    EFFICIENCY = "efficiency"  # Cost per unit, processing time
    INPUT = "input"         # Resources consumed (staff, funding)


# ── 10 Moore-Miller State Plan Priorities ──────────────────────

STATE_PLAN_PRIORITIES = {
    1: "Ending child poverty in the State of Maryland",
    2: "Setting Maryland's students up for success",
    3: "Creating an equitable, robust, and competitive economy",
    4: "Connecting Marylanders to jobs",
    5: "Creating safer communities",
    6: "Making the State of Maryland a desirable and affordable home for all residents",
    7: "Advancing infrastructure to better connect all Marylanders to opportunities and each other",
    8: "Ensuring world-class health systems for all Marylanders",
    9: "Making Maryland a leader in clean energy and the greenest state in the country",
    10: "Making Maryland a state of service",
}


@dataclass
class MFRMeasure:
    """A single performance measure from the MFR Annual Performance Report.

    This is the atomic unit for ZBB analysis — each measure links
    a budget decision unit to a measurable outcome.
    """

    # ── Identity ───────────────────────────────────────────────
    kpi_number: str              # "1.6", "2.5", "5.4" — exact reference
    measure_name: str            # Full indicator text
    priority_number: int         # 1-10, maps to STATE_PLAN_PRIORITIES
    priority_area: str           # Full priority text

    # ── Agencies ───────────────────────────────────────────────
    responsible_agency: str      # Agency that owns the program/budget
    data_source_agency: str      # Agency that reports the data (may differ)

    # ── Classification ─────────────────────────────────────────
    measure_type: str            # output, outcome, efficiency, input
    favorability_direction: str  # higher_is_favorable, lower_is_favorable, variable
    unit: str                    # percent, count, dollars, rate, days, ratio

    # ── Report Year Actuals (normalized, not fiscal year) ──────
    ry2022_actual: Optional[float] = None
    ry2023_actual: Optional[float] = None
    ry2024_actual: Optional[float] = None
    ry2025_actual: Optional[float] = None
    ry2026_actual: Optional[float] = None

    # ── Computed ───────────────────────────────────────────────
    one_year_change_pct: Optional[float] = None
    status: str = "n/a"         # strongly_favorable, favorable, stable, unfavorable, strongly_unfavorable
    five_year_trend: str = ""   # narrative: "improving", "declining", "volatile", "stable"

    # ── Targets (for ZBB justification) ────────────────────────
    target_value: Optional[float] = None
    target_year: Optional[int] = None
    target_description: str = ""

    # ── Citation ───────────────────────────────────────────────
    source_doc: str = ""
    source_page: int = 0
    footnotes: str = ""         # Any caveats or methodology notes

    # ── ZBB-specific fields ────────────────────────────────────
    is_variable: bool = False   # True for measures like SNAP enrollment
    variable_note: str = ""     # Why this measure has both favorable/unfavorable aspects


@dataclass
class MFRAgencyPlan:
    """An agency's strategic plan from the MFR document.

    Contains the agency's mission, goals, objectives — the narrative
    context needed for ZBB decision package justification.
    """

    agency_name: str
    priority_numbers: list[int] = field(default_factory=list)  # Which priorities this agency serves
    mission: str = ""
    goals: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    source_doc: str = ""
    source_page_start: int = 0
    source_page_end: int = 0


@dataclass
class ZBBDecisionUnit:
    """A decision unit for Zero-Based Budgeting.

    Combines budget data with MFR performance data to create
    a complete picture of what a program costs and what it achieves.
    This is generated by joining MFR and budget data — not extracted directly.
    """

    # ── Identity ───────────────────────────────────────────────
    agency_name: str
    program_name: str
    subprogram_name: str = ""

    # ── Budget (from fct_it_spend) ─────────────────────────────
    total_budget: float = 0.0
    general_fund: float = 0.0
    federal_fund: float = 0.0
    special_fund: float = 0.0
    yoy_change_pct: float = 0.0
    budget_trend: str = ""  # growing, shrinking, stable

    # ── Performance (from fct_mfr_performance) ─────────────────
    measures: list[MFRMeasure] = field(default_factory=list)
    favorable_count: int = 0
    unfavorable_count: int = 0
    performance_score: float = 0.0  # % favorable

    # ── ZBB Assessment ─────────────────────────────────────────
    cost_per_outcome: Optional[float] = None  # Total budget / key outcome measure
    efficiency_trend: str = ""  # improving, declining, stable
    justification_strength: str = ""  # strong, moderate, weak, insufficient_data

    # ── Priority alignment ─────────────────────────────────────
    priority_areas: list[str] = field(default_factory=list)
    governor_priority_alignment: float = 0.0  # 0-1 score
