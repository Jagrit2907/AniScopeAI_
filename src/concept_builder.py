"""Rules-based creative concept builder (no external AI service).

How it works: each selected storytelling theme maps to design levers
(character trait, conflict engine, strengths to emphasise, risks to avoid).
A seeded random choice among generic building blocks (settings, roles,
stakes) makes different inputs or a new "variation" produce a different
draft. The building blocks are deliberately generic genre ingredients, not
characters, plots or dialogue from existing works.

The output is an editable starting point — a hypothesis to test, not an
audience-validated or legally cleared concept.
"""
from __future__ import annotations

import hashlib
import random

SETTINGS = [
    "a monsoon-flooded port city run by rival trading guilds",
    "an orbital agricultural station that feeds a planet",
    "a mountain rail line where every station is its own city-state",
    "a near-future Tokyo–Mumbai research exchange programme",
    "a desert archive where history is decided by debate tournaments",
    "a floating market town that relocates every season",
    "a school for cartographers who map places that keep changing",
    "a small coastal town whose festival decides the region's water rights",
]
ROLES = ["a junior archivist", "a disgraced tactician", "a rookie insurance investigator",
         "a festival-stage engineer", "an apprentice mapmaker", "a translator between rival guilds",
         "a scholarship student", "a retired champion turned coach"]
STAKES = ["the livelihood of an entire district", "a fragile truce between two families",
          "the memory of a lost generation", "a city's access to clean water",
          "the reputation of a centuries-old institution", "the future of a failing hometown"]

THEME_LEVERS = {
    "Intelligent / strategic conflict": {
        "trait": "who wins by out-thinking stronger opponents rather than overpowering them",
        "conflict": "a season-long contest of strategy where each move reveals a hidden rule",
        "emphasise": "fair-play puzzles the audience can solve alongside the lead",
        "avoid": "solutions that rely on information hidden from the viewer"},
    "Protagonist": {
        "trait": "with a clear personal goal and a flaw that costs them on screen",
        "conflict": "a choice between personal ambition and loyalty to their team",
        "emphasise": "a lead whose decisions drive every episode",
        "avoid": "a passive lead carried by side characters"},
    "Character development": {
        "trait": "who changes visibly across the series",
        "conflict": "relationships that are tested and rebuilt over several arcs",
        "emphasise": "supporting cast with their own arcs and payoffs",
        "avoid": "characters who reset to the same state each arc"},
    "World-building": {
        "trait": "who knows one corner of the world deeply and the rest not at all",
        "conflict": "the rules of the setting itself creating the central dilemma",
        "emphasise": "consistent, discoverable rules and places",
        "avoid": "exposition dumps that stall the story"},
    "Story & premise": {
        "trait": "pulled into the premise in the first episode",
        "conflict": "a high-concept hook stated in one sentence",
        "emphasise": "a premise that can be pitched in one line",
        "avoid": "a hook that is abandoned after the opening"},
    "Emotional impact": {
        "trait": "carrying a quiet personal loss",
        "conflict": "small personal stakes that mirror the larger story",
        "emphasise": "earned emotional peaks with set-up and payoff",
        "avoid": "melodrama without groundwork"},
    "Action & fights": {
        "trait": "who fights with a distinctive, readable style",
        "conflict": "set-piece confrontations with clear stakes and geography",
        "emphasise": "choreography the audience can follow",
        "avoid": "fights that resolve by sudden new powers"},
    "Visuals & animation": {
        "trait": "linked to a strong visual motif",
        "conflict": "a world designed around a striking visual identity",
        "emphasise": "a distinctive art direction usable in merchandise",
        "avoid": "visual ambition the production budget cannot sustain"},
    "Pacing": {
        "trait": "with a goal that sets a ticking clock",
        "conflict": "a fixed deadline that keeps every episode moving",
        "emphasise": "tight arcs with regular payoffs",
        "avoid": "filler episodes and slow first arcs (a criticised aspect)"},
    "Repetitive conflicts": {
        "trait": "who must find a new approach each time",
        "conflict": "opponents who adapt, so the same trick never works twice",
        "emphasise": "escalation and variety between arcs",
        "avoid": "a repeated villain-of-the-week formula (a criticised aspect)"},
    "Humour": {
        "trait": "with a dry sense of humour that defuses tension",
        "conflict": "comic friction inside the team",
        "emphasise": "character-driven comedy",
        "avoid": "humour that undercuts serious moments"},
}
GENERIC = {"trait": "with a clear goal and a meaningful flaw", "conflict": "a goal opposed by a rival with a defensible motive",
           "emphasise": "a clear hook and consistent character motivation", "avoid": "unclear stakes"}

TITLE_A = ["Ledger", "Tide", "Signal", "Archive", "Compass", "Lantern", "Relay", "Monsoon", "Atlas", "Gambit"]
TITLE_B = ["of the Quiet City", "Protocol", "Season", "Line", "Tournament", "Accord", "Rising", "Exchange"]


def build_concept(themes: list[str], insight: str, audience_hypothesis: str, objective: str,
                  direction: str = "", variation: int = 0, criticised: list[str] | None = None) -> dict:
    seed_text = "|".join(sorted(themes)) + insight + audience_hypothesis + objective + direction + str(variation)
    rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16))
    levers = [THEME_LEVERS.get(t, GENERIC) for t in themes] or [GENERIC]
    setting = direction.strip() or rng.choice(SETTINGS)
    role = rng.choice(ROLES)
    stakes = rng.choice(STAKES)
    lead = levers[0]
    avoid = [lv["avoid"] for lv in levers]
    for c in criticised or []:
        if c in THEME_LEVERS and THEME_LEVERS[c]["avoid"] not in avoid:
            avoid.append(THEME_LEVERS[c]["avoid"])
    return {
        "working_title": f"{rng.choice(TITLE_A)} {rng.choice(TITLE_B)}",
        "core_premise": f"In {setting}, {role} becomes responsible for {stakes}.",
        "central_character": f"{role.capitalize()} {lead['trait']}.",
        "main_conflict": "; ".join(dict.fromkeys(lv["conflict"] for lv in levers[:2])).capitalize() + ".",
        "storytelling_priorities": [lv["emphasise"] for lv in levers],
        "hook": f"Can {role} protect {stakes} without becoming the kind of person they set out to stop?",
        "strengths_to_emphasise": [lv["emphasise"] for lv in levers],
        "risks_to_avoid": avoid,
        "audience_hypothesis": audience_hypothesis or "Not specified — define before testing.",
        "objective": objective,
        "why_explored": insight or "No audience insight selected: concept is exploratory only.",
        "inspired_by_themes": list(themes),
        "method": "Rules-based builder (theme → design levers + seeded generic genre blocks). No external AI used.",
        "validation_status": "Unvalidated creative hypothesis. Not audience-tested and not legally cleared.",
        "variation": variation,
    }
