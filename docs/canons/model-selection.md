# Reference: subagent model selection

Version: **1.1.0** (canon 2.5.0)

How models apply to the dev-pipeline subagents. **Normative source:** [Cursor Subagents docs](https://cursor.com/docs/subagents.md).

The orchestrator (main agent) runs on **Auto** — Cursor picks per turn. Custom subagents default to **`model: inherit`** — they use the same model as the parent agent unless you override with a specific model ID.

---

## Frontmatter rule

| Who | `model` in frontmatter |
|-----|------------------------|
| Orchestrator (main agent) | **Auto** (Cursor default for parent) |
| All custom subagents | **`inherit`** (explicit or omitted — Cursor default) |

Use a **specific model ID** in frontmatter only when a subagent must run on a particular model regardless of what the parent uses. For the standard dev pipeline, `inherit` is correct — the parent already runs on Auto and subagents inherit that context.

Materialized agents in `templates/agents/` ship `model: inherit`. Copy byte-for-byte on normalize.

---

## Tier guidance (orchestrator, not frontmatter)

These tiers describe **when the orchestrator should invest capability** in a delegation chain — not fixed slugs in `.cursor/agents/*.md`.

Put strong reasoning at the **epistemic boundaries of the chain** — the first hop and the final gate — and lighter work on mechanical middle steps.

| Tier | Pipeline roles | Why |
|------|----------------|-----|
| **Frontier reasoning** | `code-explorer`, `task-planner`, `verifier` | First hop and final gate — errors here poison everything downstream |
| **Code specialist** | `implementer` | Focused edits to a named plan step |
| **Fast / cheap** | `doc-librarian` | Mechanical doc edits from an explicit scope |

With `model: inherit`, the orchestrator's model choice flows to subagents. Pick a capable parent model when delegating frontier-reasoning agents; trivial doc work can run under any parent.

---

## Notes

- Built-in Explore / Bash handle trivial lookups without a subagent at all.
- `readonly: true` on explorers, planners, and verifiers — per Cursor docs.
- Use **single-line** `description:` strings (Cursor format). Do **not** use folded `description: >-` blocks — wrong for this cluster.
- When Cursor changes model behavior, update this doc if tier guidance shifts — no slug table to maintain in templates.
