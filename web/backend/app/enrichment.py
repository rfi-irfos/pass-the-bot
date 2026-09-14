"""Backend-side enrichment of the engine's report with human-readable display
names, per the web app design spec section 8. This is NOT a change to the
engine's own JSON contract -- the engine's report keeps returning bare
canonical ids; this module adds one field per result before the report is
handed to the browser.
"""

from __future__ import annotations

from passthebot.graph import SkillEntry

DEFAULT_DISPLAY_LANGUAGE = "en"


def add_display_names(report: dict, entries: list[SkillEntry], lang: str = DEFAULT_DISPLAY_LANGUAGE) -> dict:
    """Return a copy of report with a display_name field added to every
    entry in report['results'], looked up from the skill graph's own
    display names in the requested language. Falls back to English, then
    to the raw id, if a translation is missing (should not happen in
    practice, but never crash the API over a cosmetic field)."""
    display_by_id = {
        e.id: e.display.get(lang, e.display.get(DEFAULT_DISPLAY_LANGUAGE, e.id))
        for e in entries
    }
    enriched_results = [
        {**result, "display_name": display_by_id.get(result["id"], result["id"])}
        for result in report["results"]
    ]
    return {**report, "results": enriched_results}
