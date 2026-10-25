"""Illustrative unit economics from user-entered assumptions.

Funnel (each step is a subset of the one before, so the counts never mix):
    target audience  ->  reached (x reach rate)  ->  customers (x conversion rate)

Formulas:
    reached           = target_audience × reach_rate
    customers         = reached × conversion_rate
    gross_revenue     = customers × price
    variable_costs    = customers × variable_cost_per_unit
    contribution      = gross_revenue − variable_costs
    result_after_fixed = contribution − fixed_costs
    break_even_customers = fixed_costs ÷ (price − variable_cost_per_unit)   (if margin > 0)

Every output is an illustrative estimate based on user-entered assumptions,
not a forecast or verified market data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

FORMULAS = [
    ("Reached people", "target audience × reach rate"),
    ("Customers", "reached people × conversion rate"),
    ("Gross revenue", "customers × price"),
    ("Variable costs", "customers × variable cost per unit"),
    ("Contribution before fixed costs", "gross revenue − variable costs"),
    ("Illustrative result after fixed costs", "contribution − fixed costs"),
    ("Break-even customers", "fixed costs ÷ (price − variable cost per unit)"),
]


@dataclass
class Assumptions:
    target_audience: float = 0.0
    reach_rate_pct: float = 0.0
    conversion_rate_pct: float = 0.0
    price: float = 0.0
    variable_cost: float = 0.0
    fixed_costs: float = 0.0
    currency: str = "INR"
    duration_weeks: int = 0
    is_demo: bool = False


def validate(a: Assumptions) -> list[str]:
    errors = []
    if a.target_audience < 0:
        errors.append("Target audience cannot be negative.")
    for name, v in (("Reach rate", a.reach_rate_pct), ("Conversion rate", a.conversion_rate_pct)):
        if not 0 <= v <= 100:
            errors.append(f"{name} must be between 0% and 100%.")
    for name, v in (("Price", a.price), ("Variable cost", a.variable_cost), ("Fixed costs", a.fixed_costs)):
        if v < 0:
            errors.append(f"{name} cannot be negative.")
    if a.duration_weeks < 0:
        errors.append("Duration cannot be negative.")
    return errors


def calculate(a: Assumptions) -> dict:
    errors = validate(a)
    if errors:
        return {"errors": errors}
    reached = a.target_audience * a.reach_rate_pct / 100
    customers = reached * a.conversion_rate_pct / 100
    revenue = customers * a.price
    var_costs = customers * a.variable_cost
    contribution = revenue - var_costs
    result = contribution - a.fixed_costs
    margin = a.price - a.variable_cost
    break_even = a.fixed_costs / margin if margin > 0 else None
    warnings = []
    if margin <= 0 and a.price > 0:
        warnings.append("Price does not exceed variable cost: every sale loses money before fixed costs.")
    if customers < 1 and a.target_audience > 0:
        warnings.append("Fewer than one estimated customer — check the rates.")
    return {
        "errors": [], "warnings": warnings,
        "reached": round(reached), "customers": round(customers),
        "gross_revenue": round(revenue, 2), "variable_costs": round(var_costs, 2),
        "contribution": round(contribution, 2), "result_after_fixed": round(result, 2),
        "unit_margin": round(margin, 2),
        "break_even_customers": None if break_even is None else round(break_even),
        "label": "Illustrative estimate based on user-entered assumptions — not a forecast or market data.",
    }


def as_dict(a: Assumptions) -> dict:
    return asdict(a)
