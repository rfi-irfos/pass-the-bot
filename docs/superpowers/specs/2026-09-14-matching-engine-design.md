# passthebot — Matching Engine Design

**Status:** Draft, pending user review
**Scope:** This spec covers ONLY the core matching engine (the shared kernel). The
two downstream products — the free/open-source candidate CV checker and the
monetizable KMU decision-support agent — are separate sub-projects, each with
their own spec once this engine exists. Do not build either frontend as part
of implementing this spec.

## 1. Problem

Automated resume screening (ATS-style keyword filters) rejects qualified
candidates on pure surface-form keyword mismatch (e.g. "Node" vs "Node.js",
"Python" vs "python"). Bolting an LLM "explainer" onto a black-box
deterministic pipeline does not fix this: the root cause is that the matching
step has no concept of keyword equivalence classes. This engine is the fix:
a deterministic, explainable matching kernel where "is X the same skill as Y"
is answered by a versioned, inspectable data structure, not a model call.

## 2. Users of this engine (for context, not built here)

- **Candidate checker (OSS, free):** upload CV + job posting, get a score and
  suggestions on what to add/rephrase. Positioned as a lead-magnet / dogfood
  / brand-building tool ("how visible is your CV").
- **KMU agent (paid):** decision-support for small/medium employers screening
  real candidates. Classified under **EU AI Act Annex III (high-risk,
  recruitment/CV-screening)** — obligations apply from 2027-12-02. Design
  consequence for this engine: every output must be traceable to a specific,
  versioned decision (see section 5), and no component of this engine may
  itself issue an automated accept/reject — that decision always stays with
  a human (HITL), enforced at the product layer, not re-litigated here.

## 3. Components

1. **Skill Graph** (data) — versioned YAML files, one per category
   (`languages`, `frameworks`, `tools`, `certifications`, `job_titles`,
   `hard_skills`, `soft_skills`), living in this repo under `data/skills/`.
   Community-contributable via normal PR review.
2. **Normalizer** — scans raw input text against every alias in the graph.
   Pure dictionary/string-matching for discrete categories, no model call.
   Embedding similarity against anchor phrases for `soft_skills` only.
3. **Matcher/Scorer** — deterministic kernel. Compares the posting's required
   keyword set against the resume's extracted keyword set by canonical ID.
   Zero LLM involvement.
4. **Report Builder** — aggregates results into the versioned JSON contract
   (section 6). This JSON is the engine's actual deliverable; everything
   downstream (both frontends) consumes only this.
5. **Explainer (out of scope here, business-layer only)** — an LLM step that
   turns an already-computed JSON report into human-readable prose for the
   KMU dashboard. Runs strictly after the Report Builder, never before, never
   influences matching. Not implemented as part of this spec; noted so the
   JSON contract stays stable enough to support it later without a rewrite.
6. **Curation Pipeline** (async, out of the live request path) — frequently
   unmatched terms are logged to a queue. A periodic job proposes new graph
   entries (`status: ai-suggested-pending`) as a PR; a human approves before
   the entry affects matching.

## 4. Data model

One YAML file per category under `data/skills/`.

Discrete categories (`languages`, `frameworks`, `tools`, `certifications`,
`job_titles`, `hard_skills`):
```yaml
- id: nodejs
  category: languages
  display: { de: "Node.js", en: "Node.js" }
  aliases: ["Node.js", "Node", "NodeJS", "nodejs", "node js"]
  status: curated          # curated | ai-suggested-pending | ai-suggested-approved
  added: "2026-09-14"
```
`aliases` is a single flat, language-agnostic list — this also resolves
cross-language equivalents for free (e.g. "Wirtschaftsinformatik" /
"Business Informatics" as two aliases of one `job_titles`/`certifications`
entry) without a separate mechanism.

`soft_skills` (embedding-based, different shape):
```yaml
- id: teamwork
  category: soft_skills
  display: { de: "Teamfähigkeit", en: "Team player" }
  anchor_phrases: ["Teamfähigkeit", "teamorientiert arbeiten", "team player", "works well in teams", "collaborative"]
  embedding_threshold: 0.75
  status: curated
```

**Validation invariants (enforced in CI, see section 7):**
- `id` unique across the entire graph (not just within a category).
- No alias/anchor-phrase string (after normalization: lowercase, strip
  punctuation/whitespace variants) claimed by two different `id`s.
- `category` must be one of the seven enum values above.
- `status` must be one of `curated` / `ai-suggested-pending` /
  `ai-suggested-approved`. Only `curated` and `ai-suggested-approved` entries
  are eligible for matching; `ai-suggested-pending` is inert until a human
  changes its status via reviewed PR.

## 5. Data flow

1. **Input:** raw text of a job posting and raw text of a resume. This spec
   only covers plain text in; PDF/DOCX extraction is the calling frontend's
   job, not the engine's.
2. **Normalizer** scans both texts against the full alias/anchor-phrase set,
   producing two extracted keyword sets: `{id, category, matched_text,
   confidence}` for posting and resume independently.
3. **Requirement-level detection (posting only, V1 heuristic):** a simple
   proximity check for phrases like "erforderlich" / "must have" / "zwingend"
   vs. "von Vorteil" / "nice to have" / "wünschenswert" near an extracted
   keyword, defaulting to `required: true` when no signal is found. This is
   intentionally simple for V1; refining it is a later iteration, not a
   blocker for shipping the rest.
4. **Matcher** compares the posting's extracted set against the resume's, per
   canonical ID:
   - Same ID present in both → `MATCH`.
   - Not present, but a fuzzy-string (discrete categories) or embedding
     (soft skills) hit clears a lower confidence threshold → `NEAR_MISS`,
     always labeled as unconfirmed, with a suggested canonical form.
   - No hit at any threshold → `MISSING`.
5. **Report Builder** aggregates into the JSON contract (section 6),
   including `graph_version` (the git commit hash of `data/skills/` at
   matching time) for full audit traceability.

## 6. Output contract

```json
{
  "engine_version": "0.1.0",
  "graph_version": "<git-commit-hash-of-data/skills-at-match-time>",
  "results": [
    {"id": "nodejs", "category": "languages", "status": "MISSING", "required": true},
    {"id": "python", "category": "languages", "status": "MATCH", "required": true},
    {"id": "docker", "category": "tools", "status": "NEAR_MISS", "required": false,
     "found_text": "dockr", "suggested_alias": "Docker", "confidence": 0.82}
  ],
  "score": {"required_matched": 4, "required_total": 6, "coverage_pct": 66.7}
}
```
`graph_version` is mandatory on every report, not optional metadata — it is
what makes a report re-derivable and auditable later (load-bearing for the
KMU/AI-Act use case, harmless overhead for the free checker).

## 7. Error handling / edge cases

- Empty or unparseable input text → explicit error result, never a silent
  empty/zero report (which would misleadingly read as "no skills found").
- Alias/ID collisions in the graph → CI validation script rejects the PR
  before merge; never a runtime concern.
- Frequently-seen unmatched terms are always logged to the curation queue,
  never silently dropped (mirrors the "no silent omission" standard this
  team already holds itself to elsewhere).
- Cross-category ambiguity (a string that plausibly belongs to two
  categories) is resolved by the `category` field on each graph entry, and
  the same CI validation catches any alias accidentally duplicated across
  categories.

## 8. Testing strategy

- **Golden-file tests:** a checked-in set of realistic job-posting/resume
  text pairs with hand-verified expected reports; run on every change to the
  matcher code or the skill graph.
- **Graph validation tests:** enforce every invariant in section 4 (unique
  IDs, no alias collisions, valid enums) — this is what runs in CI on every
  PR to `data/skills/`, including community-submitted ones.
- **Regression case, explicit:** a resume containing "Java" against a
  posting requiring "JavaScript" must resolve to `MISSING` for JavaScript,
  not a false-positive match — the two are frequently confused strings but
  are not the same skill and must never share an alias.

## 9. Explicitly out of scope for this spec

- The candidate-facing checker UI/site.
- The KMU-facing agent/dashboard and its Explainer LLM step.
- The hierarchical skill taxonomy (parent/child/adjacent-skill relations) —
  a real future extension once the flat equivalence-class version has
  shipped and proven out; deliberately not built now (YAGNI).
- PDF/DOCX text extraction.
- The automated PR-proposal bot for the curation pipeline (section 3.6) —
  the *data shape* it writes into (`status: ai-suggested-pending`) is
  specified here so the schema doesn't need to change later, but the bot
  itself is a follow-on project.
