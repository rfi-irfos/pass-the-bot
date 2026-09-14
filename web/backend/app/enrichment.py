"""Backend-side enrichment of the engine's report with human-readable display
names, per the web app design spec section 8. This is NOT a change to the
engine's own JSON contract -- the engine's report keeps returning bare
canonical ids; this module adds one field per result before the report is
handed to the browser.
"""

from __future__ import annotations

from passthebot.graph import SkillEntry

DISPLAY_LANGUAGE = "en"  # matches the frontend's language, see spec section 9


def add_display_names(report: dict, entries: list[SkillEntry]) -> dict:
    """Return a copy of report with a display_name field added to every
    entry in report['results'], looked up from the skill graph's own
    display names. Falls back to the raw id if an entry is somehow not
    found in the graph (should not happen in practice, but never crash the
    API over a cosmetic field)."""
    display_by_id = {e.id: e.display.get(DISPLAY_LANGUAGE, e.id) for e in entries}
    enriched_results = [
        {**result, "display_name": display_by_id.get(result["id"], result["id"])}
        for result in report["results"]
    ]
    return {**report, "results": enriched_results}
