# Candidate checker frontend — early notes (2026-09-14)

Captured during matching-engine implementation, for use when this sub-project
gets its own brainstorming/spec cycle (per design doc section 9 — do not
build any of this until the engine ships and this gets its own spec).

## Scope clarification vs. competitors (Enhancv)

Enhancv (enhancv.com/resources/resume-checker) is a resume **builder/editor**
with an ATS-check bolted on, gated behind the Pro plan (€19.67/mo quarterly).
Free plan caps out at 12 section items.

passthebot's candidate checker is explicitly **not** a builder/rewriter. It
only answers: how does the matching engine see this resume against this
posting, what's the score/coverage, what specifically is missing or
near-missing, how likely is this to clear a keyword filter. No editing, no
templates, no "improve my wording" AI rewrite. Diagnostic tool, not an
authoring tool. Free with no artificial caps (no "max 12 items" style limit)
is the intended contrast, not a growth-hack free tier.

## Design direction (Simeon, 2026-09-14, reacting to Enhancv's site)

- Single tool, single page, single problem/solution — no nested site
  structure, no multi-page navigation to dig through.
- Clean, plain white background, generous whitespace, large/legible fonts.
- Upload form front and center (resume + job posting), verdict/score
  displayed clearly and immediately after processing.
- SPA (single-page app) feel: intuitive, fast, no friction, well-designed
  but minimal — the opposite of a feature-crowded dashboard.
- Liked Enhancv's visual polish/simplicity as a UI *reference*, explicitly
  not its scope (builder) or its pricing model (paywalled ATS check).
