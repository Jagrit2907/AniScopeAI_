from src.business_calculator import Assumptions, calculate


def test_funnel_and_formulas():
    r = calculate(Assumptions(target_audience=100_000, reach_rate_pct=10, conversion_rate_pct=5,
                              price=500, variable_cost=200, fixed_costs=100_000))
    assert r["reached"] == 10_000 and r["customers"] == 500
    assert r["gross_revenue"] == 250_000 and r["variable_costs"] == 100_000
    assert r["contribution"] == 150_000 and r["result_after_fixed"] == 50_000
    assert r["break_even_customers"] == 333


def test_invalid_inputs_rejected():
    r = calculate(Assumptions(target_audience=-1, reach_rate_pct=120, conversion_rate_pct=5, price=-3))
    assert len(r["errors"]) == 3


def test_negative_margin_warns_and_no_break_even():
    r = calculate(Assumptions(target_audience=1000, reach_rate_pct=50, conversion_rate_pct=10,
                              price=100, variable_cost=150, fixed_costs=10))
    assert r["break_even_customers"] is None and r["warnings"]
