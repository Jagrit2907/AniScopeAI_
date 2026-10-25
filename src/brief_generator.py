"""Assemble the Opportunity Brief from the current workspace.

Pure function of its inputs (no Streamlit), so it is unit-testable. Every
section states what evidence exists; missing inputs become explicit gaps in
"Risks and limitations" and "Next steps" rather than invented content.
"""
from __future__ import annotations

from datetime import datetime


def _fmt_money(v, cur):
    return "—" if v is None else f"{cur} {v:,.0f}"


def build_brief(*, title: dict | None, trend: dict | None, evidence: dict | None,
                aspects: list[dict] | None, finding: dict | None, concept: dict | None,
                plan: dict | None, assumptions: dict | None, calc: dict | None,
                validation: dict | None, catalog_source: str) -> dict:
    gaps: list[str] = []
    sections: dict[str, list[str]] = {}
    name = title["title"] if title else "No title selected"

    # 2. Title and market context
    ctx = []
    if title:
        meta = ", ".join(f"{k}: {v}" for k, v in (("Type", title.get("type")), ("Year", title.get("year")),
                                                     ("Episodes", title.get("episodes")), ("Status", title.get("status")))
                         if v not in (None, "", "nan", "<NA>"))
        ctx.append(f"{name} — {meta or 'limited metadata'} (catalog: {catalog_source}).")
        if title.get("score") not in (None, "", "nan"):
            ctx.append(f"Cross-site aggregate catalog score: {float(title['score']):.2f}/10 (global users, not India-specific).")
        if title.get("visibility"):
            ctx.append("Visibility: " + title["visibility"])
        if title.get("tags"):
            ctx.append("Catalog tags: " + ", ".join(title["tags"][:10]) + ".")
    else:
        gaps.append("No title selected; the brief is not anchored to a specific anime.")
    if trend and trend.get("abs_change") is not None:
        ctx.append(f"Observed trend ({trend.get('geo') or 'geography unspecified'}): {trend['explanation']} "
                   f"Reliability: {trend['reliability']}.")
        if trend["reliability"] != "sufficient":
            gaps.append(f"Trend evidence reliability is '{trend['reliability']}'.")
    else:
        ctx.append("No usable dated trend observations for this title.")
        gaps.append("No India trend observations: attention growth in India is not established.")
    sections["Title and market context"] = ctx

    # 3. Audience evidence
    ae = []
    if evidence and evidence.get("records"):
        ae.append(f"{evidence['records']} review records from {', '.join(evidence['sources'])}"
                  + (f", dated {evidence['date_min']} to {evidence['date_max']}." if evidence.get("date_min") else "."))
        if evidence.get("india_tagged", 0) == 0:
            ae.append("None of these records is tagged as Indian; they describe general (international) reviewer response.")
            gaps.append("Review evidence is not India-specific.")
        for a in (aspects or [])[:6]:
            ae.append(f"{a['aspect']}: {a['stance']} ({a['positive']} reviews praising / {a['negative']} criticising, "
                      f"of {a['reviews']} reviews mentioning it).")
    else:
        ae.append("No review evidence is loaded for this title.")
        gaps.append("No audience review evidence: storytelling strengths and weaknesses are unknown.")
    sections["Audience evidence"] = ae

    # 4. Opportunity hypothesis
    hyp = []
    if finding:
        hyp.append(f"Finding used: {finding.get('summary')}")
    if plan and plan.get("hypothesis"):
        hyp.append(f"Hypothesis (unvalidated): {plan['hypothesis']}")
    if not hyp:
        hyp.append("No opportunity hypothesis has been defined yet.")
        gaps.append("No opportunity hypothesis defined in the Business Opportunity Planner.")
    sections["Opportunity hypothesis"] = hyp

    # 5. Proposed offering
    off = []
    if concept:
        off.append(f"Creative concept '{concept.get('working_title')}': {concept.get('core_premise')} "
                   f"Inspired by themes: {', '.join(concept.get('inspired_by_themes') or ['none'])}. "
                   f"Status: {concept.get('validation_status')}")
    if plan:
        for area in ("localization", "monetization", "distribution", "retention"):
            items = plan.get(area) or []
            note = plan.get(f"{area}_note")
            if items or note:
                off.append(f"{area.capitalize()}: {', '.join(items)}" + (f" — {note}" if note else ""))
    if not off:
        off.append("No offering selected yet.")
        gaps.append("No offering selected.")
    sections["Proposed offering"] = off

    # 6. Commercial assumptions
    com = []
    if assumptions and calc and not calc.get("errors"):
        cur = assumptions.get("currency", "INR")
        tag = " (editable demo values)" if assumptions.get("is_demo") else ""
        com.append(f"User-entered assumptions{tag}: target audience {assumptions['target_audience']:,.0f}; "
                   f"reach {assumptions['reach_rate_pct']}%; conversion {assumptions['conversion_rate_pct']}%; "
                   f"price {_fmt_money(assumptions['price'], cur)}; variable cost {_fmt_money(assumptions['variable_cost'], cur)}; "
                   f"fixed costs {_fmt_money(assumptions['fixed_costs'], cur)}.")
        com.append(f"Illustrative outputs: {calc['reached']:,} reached → {calc['customers']:,} customers; "
                   f"gross revenue {_fmt_money(calc['gross_revenue'], cur)}; contribution {_fmt_money(calc['contribution'], cur)}; "
                   f"result after fixed costs {_fmt_money(calc['result_after_fixed'], cur)}.")
        com.append(calc["label"])
        if assumptions.get("is_demo"):
            gaps.append("Commercial figures use demo assumptions, not researched inputs.")
    else:
        com.append("No commercial assumptions entered.")
        gaps.append("Commercial viability not explored.")
    sections["Commercial assumptions"] = com

    # 7. Validation experiment
    val = []
    if validation and any(validation.values()):
        for k in ("hypothesis", "audience", "method", "offer", "metric", "threshold", "risks", "unknowns"):
            if validation.get(k):
                val.append(f"{k.capitalize()}: {validation[k]}")
    else:
        val.append("No validation experiment defined.")
        gaps.append("No validation experiment defined.")
    sections["Validation experiment"] = val

    # 8 / 9
    sections["Risks and limitations"] = gaps + [
        "AniScope findings are decision support, not independent verification.",
        "Search interest and review sentiment do not measure purchase intent or revenue.",
        "Licensing, distribution rights and partner availability have not been verified.",
    ]
    steps = []
    if any("trend" in g.lower() for g in gaps):
        steps.append("Export Google Trends (India) for this title plus an anchor title and import it.")
    if any("review" in g.lower() for g in gaps):
        steps.append("Import permitted review evidence (e.g. AniList API) for this title.")
    if any("india" in g.lower() for g in gaps):
        steps.append("Run a short survey or community poll with Indian fans to test the key finding.")
    if any("validation" in g.lower() for g in gaps):
        steps.append("Define a small validation experiment with a measurable success threshold.")
    steps.append("Confirm licensing and distribution rights before any external commitment.")
    sections["Next steps"] = steps

    # 1. Executive summary (written last, from what exists)
    have = [k for k, v in (("trend observations", trend and trend.get("abs_change") is not None),
                           ("review evidence", evidence and evidence.get("records")),
                           ("a creative concept", concept), ("commercial assumptions", calc and not calc.get("errors")))
            if v]
    summary = f"This brief investigates a possible opportunity around {name}. "
    summary += ("It draws on " + ", ".join(have) + ". ") if have else "It currently has no supporting evidence beyond catalog metadata. "
    summary += f"{len(gaps)} evidence gap(s) are listed under Risks and limitations; findings are hypotheses for validation, not conclusions."
    ordered = {"Executive summary": [summary]}
    ordered.update(sections)
    return {"title": f"Opportunity Brief — {name}", "generated_at": datetime.now().strftime("%d %b %Y, %H:%M"),
            "sections": ordered, "gaps": gaps}


def to_markdown(brief: dict) -> str:
    lines = [f"# {brief['title']}", f"_Generated {brief['generated_at']} by AniScope AI. Not independently verified._", ""]
    for i, (head, items) in enumerate(brief["sections"].items(), 1):
        lines.append(f"## {i}. {head}")
        lines += [f"- {x}" for x in items] if len(items) > 1 else items
        lines.append("")
    return "\n".join(lines)
