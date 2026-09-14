# passthebot — matching engine

A deterministic, explainable keyword-matching kernel for CV/job-posting
screening. Automated resume screening (ATS keyword filters) rejects
qualified candidates on pure surface-form mismatch (e.g. "Node" vs
"Node.js", "Python" vs "python"). This engine fixes the root cause: "is
skill X the same as skill Y" is answered by a versioned, inspectable skill
graph (YAML data), not a model call or a fuzzy string heuristic alone.
Discrete skills (languages, frameworks, tools, certifications, job titles,
hard skills) are matched by normalized alias lookup; soft skills are
matched by embedding similarity against curated anchor phrases. See
`docs/superpowers/specs/2026-09-14-matching-engine-design.md` for the full
design spec.

This repository ships only the engine (the shared kernel). The two
downstream products — a free/open-source CV checker and a paid
decision-support agent for employers — are separate projects that consume
this engine's JSON report contract.

## Usage

The single entry point is `run_pipeline`:

```python
from passthebot.pipeline import run_pipeline

report = run_pipeline(
    posting_text="Requires Python and Docker experience.",
    resume_text="Experienced Python developer, Docker in production.",
    required_ids={"python", "docker"},
)

print(report["score"]["coverage_pct"])
print(report["results"])
```

`data_dir` and `repo_root` are optional and default to the skill graph
bundled inside the installed package and this repo's root, respectively.
Pass them explicitly only if you need to point at a different skill graph
or a different repo checkout (e.g. in tests). An optional `embedder`
(`passthebot.embeddings.Embedder`) can be passed in to reuse an
already-loaded model across calls instead of loading one per call.

The returned report is a plain JSON-serializable `dict` containing
`engine_version`, `graph_version` (the repo's git HEAD commit, for audit
trail), `model_version` (the embedding model identity used for soft-skill
matching), per-keyword `results`, and a `score` summary.

Validate the skill graph on its own (also run in CI on every PR):

```bash
python3 -m passthebot.validate_graph
```

## Adding a new skill graph entry

Skill data lives in `src/passthebot/data/skills/*.yaml`, one file per
category. See the design spec's section 4 ("Data model") for the exact
YAML schema for discrete categories (`aliases`, matched by exact
normalized substring) versus `soft_skills` (`anchor_phrases` +
`embedding_threshold`, matched by embedding similarity).

New entries should generally be added with `status: curated` via a normal
PR. Entries with `status: ai-suggested-pending` are inert — loaded but
excluded from matching (see `passthebot.graph.active_entries`) — until a
human reviews and flips the status to `ai-suggested-approved`, per the
design spec's human-in-the-loop requirement. CI validates every PR via
`python3 -m passthebot.validate_graph`, which rejects duplicate ids,
invalid categories/statuses, and alias/anchor-phrase collisions across
different ids.
