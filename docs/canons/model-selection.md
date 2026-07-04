# Reference: subagent model selection

Version: **1.0.0** (canon 2.5.0)

How to assign models to the dev-pipeline subagents. The orchestrator (main agent) runs on **Auto** — Cursor picks per turn. Subagents get **fixed** models, because their role is stable and predictable.

Model names churn; pick by **tier**, then map the tier to whatever current Cursor model fits. Keep the frontmatter slug matching Cursor's current identifier.

---

## The principle

Put strong models at the **epistemic boundaries of the chain** — the first hop and the final gate — and cheaper models on mechanical middle work.

An error at one hop multiplies down the chain: a weak `code-explorer` feeds a wrong map to the planner, who feeds a wrong plan to the implementer. A weak `verifier` waves through work that was never done. Those two positions are where capability pays for itself; the middle can be lighter.

---

## Tiers

| Tier | Use for | Current Cursor picks (2026-07) |
|------|---------|--------------------------------|
| **Frontier reasoning** | Impact analysis, planning, skeptical verification, architecture | Opus 4.8, Sonnet 5, GPT-5.5, Gemini 3.1 Pro |
| **Code specialist** | Writing/editing code to a spec | Codex 5.3, Codex 5.1 Max |
| **Fast / cheap** | Mechanical edits, doc formatting, trivial lookups | Haiku 4.5, Composer 2.5, Gemini 3.5 Flash |

---

## Role → tier

| Agent | Tier | Why | `model:` (Cursor slug) |
|-------|------|-----|------------------------|
| `code-explorer` | Frontier reasoning | First hop — its map gates everything downstream | `gemini-3.1-pro` |
| `task-planner` | Frontier reasoning | Plan quality makes or breaks the pipeline | `gpt-5.5` |
| `implementer` | Code specialist | Focused code changes to a named step | `gpt-5.3-codex` |
| `verifier` | Frontier reasoning | Final gate — a weak critic rubber-stamps | `claude-sonnet-5` |
| `doc-librarian` | Fast / cheap | Mechanical doc edits from an explicit scope | `claude-haiku-4-5` |

Orchestrator: **Auto** (it triages, delegates, and reviews the plan — variety of turn types suits Auto).

The `model:` value is the **exact Cursor picker slug** — this table is its single source of truth. Cursor's naming is not uniform (`gemini-3.1-pro`, `gpt-5.5`, but `gpt-5.3-codex`, `claude-sonnet-5`, `claude-haiku-4-5`); use it verbatim, no shorthand and no suffix. A shorthand slug forces the materializing agent to hand-edit frontmatter, which is where corruption creeps in — so the slug here must match what the template ships, and templates are copied byte-for-byte.

---

## Notes

- Built-in Explore / Bash handle trivial lookups without a subagent at all.
- Raise a tier when a repo is large or unusually subtle; drop one when tasks are routine and cost matters.
- When Cursor renames or retires a model, update the slug column here **and** the `model:` field in the matching `templates/agents/*.md` in the same pass, so template and canon never drift — the tier mapping stays.
