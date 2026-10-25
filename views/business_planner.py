"""Screen 5 — Business Opportunity Planner."""
import plotly.graph_objects as go
import streamlit as st

from components import Shinigami
from components.styles import TEAL, label, page_header
from src import app_data, catalog_service, state
from src.business_calculator import FORMULAS, Assumptions, as_dict, calculate

page_header("Localization · Monetization · Distribution · Retention", "Business Opportunity Planner",
            "Shape a possible offer, make every assumption explicit, and decide what to validate before committing resources.")

df = app_data.catalog()
rec = catalog_service.get_record(df, st.session_state.get("selected_anime_id")) if df is not None else None
finding = st.session_state.get("selected_finding")
concept = st.session_state.get("concept")
plan = dict(st.session_state.get("plan") or {})
saved_a = st.session_state.get("assumptions") or {}

AREAS = {
    "localization": ("Localization", [
        "Hindi subtitle test", "Regional-language subtitle test (e.g. Tamil, Telugu, Bengali)", "Hindi dub pilot episode",
        "Localized trailer and key art", "Cultural-context explainer content", "Indian creator co-hosted watch-through",
        "Regional campaign in one metro first"],
        "Hypotheses about language or messaging to test. AniScope has no verified data on Indian language preferences."),
    "monetization": ("Monetization & Merchandise", [
        "Licensed apparel", "Limited-edition collectible", "Art book / print", "Digital wallpaper or sticker pack (micropayment)",
        "Ad-supported free episodes", "Paid fan event / screening", "Premium community membership", "Co-branded product with a local brand"],
        "Illustrative offers. No licence, supplier or partnership is implied to exist."),
    "distribution": ("Distribution", [
        "Short-form clips on social video platforms", "Partnership with Indian anime creators / communities",
        "College club and campus events", "Comic-con / pop-culture event presence", "E-commerce marketplace storefront",
        "Streaming platform availability check (licensing question)", "Small-scale landing-page demand test"],
        "Promotional distribution is separate from content licensing; neither has been verified."),
    "retention": ("Community Retention", [
        "Weekly episode discussion threads", "Fan art / cosplay challenges", "Recurring limited drops",
        "Loyalty points for repeat purchases", "Members-only events", "Seasonal anniversary campaign"],
        "Proposed metrics only: repeat participation, returning users, repeat purchase rate. No outcomes are observed."),
}

cautions = []
if not finding:
    cautions.append("No audience finding is attached — this plan is not evidence-led yet.")
if not saved_a or saved_a.get("is_demo"):
    cautions.append("Revenue figures depend entirely on the assumptions you enter.")
Shinigami.speak(cautions, [], "Pick a starting point, choose offers in each area, then test the economics with your own assumptions.")

# ----------------------------------------------------------- start point ----
st.markdown("#### 1 · Starting point and hypothesis")
with st.container(border=True):
    starts = ["Selected title", "Audience finding", "Creative concept", "Manual business idea"]
    start = st.radio("Start from", starts, horizontal=True, index=starts.index(plan.get("start", "Selected title")))
    if start == "Selected title":
        st.markdown(f"{label('observed')} {rec['title']}" if rec is not None
                    else "No title selected — choose one in the Command Center.", unsafe_allow_html=True)
    elif start == "Audience finding":
        st.markdown(f"{label('observed')} {finding['summary']}" if finding
                    else "No finding selected in Audience Intelligence.", unsafe_allow_html=True)
    elif start == "Creative concept":
        st.markdown(f"{label('hyp')} **{concept['working_title']}** — {concept['core_premise']}" if concept
                    else "No concept built in the Creative Lab.", unsafe_allow_html=True)
    manual = st.text_input("Business idea", plan.get("manual_idea", ""), disabled=start != "Manual business idea")
    example_h = (f"e.g. Indian fans of {rec['title']} will engage with an offer built around "
                 f"{', '.join((finding or {}).get('praised') or ['its strongest themes'])}." if rec is not None
                 else "e.g. Indian college fans will pre-order a limited art print")
    hypothesis = st.text_area("Opportunity hypothesis (unvalidated)", plan.get("hypothesis", ""), height=70,
                              placeholder=example_h)

# ----------------------------------------------------------- four areas ----
st.markdown("#### 2 · Offer design")
new_plan = {"start": start, "manual_idea": manual, "hypothesis": hypothesis}
tabs = st.tabs([v[0] for v in AREAS.values()])
for tab, (key, (title, opts, note)) in zip(tabs, AREAS.items()):
    with tab:
        st.caption(note)
        new_plan[key] = st.multiselect(f"{title} options", opts, default=[o for o in plan.get(key, []) if o in opts], key=f"bp_{key}")
        new_plan[f"{key}_note"] = st.text_area("Notes / rationale", plan.get(f"{key}_note", ""), key=f"bp_{key}_note", height=70)
if new_plan != st.session_state.get("plan"):
    st.session_state["plan"] = new_plan
    state.save_workspace()

# ----------------------------------------------------------- calculator ----
st.markdown(f"#### 3 · Illustrative economics {label('assume')}", unsafe_allow_html=True)
DEMO = dict(target_audience=200_000.0, reach_rate_pct=10.0, conversion_rate_pct=2.0, price=799.0,
            variable_cost=350.0, fixed_costs=150_000.0, currency="INR", duration_weeks=8, is_demo=True)
d1, d2 = st.columns([1, 4])
if d1.button("Load demo assumptions"):
    st.session_state["assumptions"] = DEMO
    for k, v in DEMO.items():
        st.session_state[f"calc_{k}"] = v
    st.rerun()
d2.caption("Demo values are arbitrary, editable placeholders to show how the calculator works — not Indian market data.")
src_a = st.session_state.get("assumptions") or {}
_defaults = {"currency": "INR", "target_audience": 0.0, "reach_rate_pct": 0.0, "conversion_rate_pct": 0.0,
             "price": 0.0, "variable_cost": 0.0, "fixed_costs": 0.0, "duration_weeks": 0}
for k, v in _defaults.items():
    if f"calc_{k}" not in st.session_state:  # seed widgets once from the saved workspace
        st.session_state[f"calc_{k}"] = type(v)(src_a.get(k, v))
with st.container(border=True):
    c = st.columns(4)
    cur = c[0].selectbox("Currency", ["INR", "JPY", "USD"], key="calc_currency")
    ta = c[1].number_input("Target audience (people)", 0.0, 1e10, step=1000.0, key="calc_target_audience",
                           help="The total group the offer is aimed at — your own estimate, with its source noted below.")
    rr = c[2].number_input("Reach rate (%)", 0.0, 100.0, step=0.5, key="calc_reach_rate_pct",
                           help="Share of the target audience the campaign actually reaches.")
    cr = c[3].number_input("Conversion rate (%)", 0.0, 100.0, step=0.1, key="calc_conversion_rate_pct",
                           help="Share of reached people who buy.")
    c = st.columns(4)
    pr = c[0].number_input(f"Price per unit ({cur})", 0.0, 1e9, step=10.0, key="calc_price")
    vc = c[1].number_input(f"Variable cost per unit ({cur})", 0.0, 1e9, step=10.0, key="calc_variable_cost")
    fc = c[2].number_input(f"Fixed campaign / development cost ({cur})", 0.0, 1e12, step=1000.0, key="calc_fixed_costs")
    du = c[3].number_input("Campaign duration (weeks)", 0, 520, key="calc_duration_weeks")
    a = Assumptions(ta, rr, cr, pr, vc, fc, cur, int(du),
                    is_demo=bool(src_a.get("is_demo")) and all(
                        float(src_a.get(k, -1)) == v for k, v in (("target_audience", ta), ("reach_rate_pct", rr),
                                                                  ("conversion_rate_pct", cr), ("price", pr),
                                                                  ("variable_cost", vc), ("fixed_costs", fc))))
    if as_dict(a) != src_a:
        st.session_state["assumptions"] = as_dict(a)
        state.save_workspace()
    res = calculate(a)
    if res["errors"]:
        for e in res["errors"]:
            st.error(e)
    elif ta == 0:
        st.info("Enter a target audience and rates to see illustrative results.")
    else:
        if a.is_demo:
            st.warning("Showing DEMO assumptions. Replace them with researched figures before using the results.")
        for w in res["warnings"]:
            st.warning(w)
        m = st.columns(5)
        m[0].metric("Reached people", f"{res['reached']:,}")
        m[1].metric("Customers", f"{res['customers']:,}")
        m[2].metric("Gross revenue", f"{cur} {res['gross_revenue']:,.0f}")
        m[3].metric("Contribution", f"{cur} {res['contribution']:,.0f}")
        m[4].metric("Result after fixed costs", f"{cur} {res['result_after_fixed']:,.0f}")
        st.caption(res["label"] + (f" Break-even: about {res['break_even_customers']:,} customers." if res["break_even_customers"] else ""))
        fig = go.Figure(go.Funnel(y=["Target audience", "Reached", "Customers"], x=[ta, res["reached"], res["customers"]],
                                  marker=dict(color=["#273449", "#3B6EA8", TEAL]), textinfo="value+percent initial"))
        fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with st.expander("Formulas used"):
        st.markdown("".join(f'<div class="as-formula">{n} = {f}</div>' for n, f in FORMULAS), unsafe_allow_html=True)
    plan_src = st.text_input("Where do these assumptions come from?", plan.get("assumption_source", ""),
                             placeholder="e.g. team estimate; survey of 60 students; partner quote")
    if plan_src != st.session_state["plan"].get("assumption_source", ""):
        st.session_state["plan"]["assumption_source"] = plan_src
        state.save_workspace()

# ------------------------------------------------------- validation plan ----
st.markdown(f"#### 4 · Validation experiment {label('hyp')}", unsafe_allow_html=True)
vp = dict(st.session_state.get("validation_plan") or {})
if st.button("Suggest a plan from my selections"):
    offer = (new_plan.get("monetization") or new_plan.get("distribution") or new_plan.get("localization") or ["the proposed offer"])[0]
    vp = {"hypothesis": hypothesis,
          "audience": "Indian fans reachable through one channel (e.g. a college club or creator community)",
          "method": f"Two-week landing-page / pre-order test for '{offer}', with one localized and one standard message (A/B).",
          "offer": offer,
          "metric": "Sign-up or pre-order rate per visitor; compare localized vs standard message.",
          "threshold": "Decide the threshold before the test (e.g. pre-order rate above the conversion rate assumed in the calculator).",
          "risks": "Small, self-selected sample; campus audience may not represent wider India; licensing not yet confirmed.",
          "unknowns": "Willingness to pay at scale; regional differences; partner availability."}
    for k, v in vp.items():
        st.session_state[f"vp_{k}"] = v
for k in ("hypothesis", "audience", "method", "offer", "metric", "threshold", "risks", "unknowns"):
    st.session_state.setdefault(f"vp_{k}", vp.get(k, ""))
with st.container(border=True):
    fields = [("hypothesis", "Hypothesis"), ("audience", "Target audience"), ("method", "Test method"),
              ("offer", "Proposed offer or message"), ("metric", "Success metric"),
              ("threshold", "Result that justifies further investigation"), ("risks", "Major risks"), ("unknowns", "Remaining unknowns")]
    new_vp = {}
    cols = st.columns(2)
    for i, (k, lab) in enumerate(fields):
        new_vp[k] = cols[i % 2].text_area(lab, key=f"vp_{k}", height=80)
    if new_vp != st.session_state.get("validation_plan"):
        st.session_state["validation_plan"] = new_vp
        state.save_workspace()
    st.caption("No experiment has been run. Results must come from a real test, never from this tool.")
st.page_link("views/opportunity_brief.py", label="Generate the Opportunity Brief →", icon=":material/description:")
