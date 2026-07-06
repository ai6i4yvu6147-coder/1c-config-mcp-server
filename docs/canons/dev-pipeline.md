# Canon: dev pipeline (subagents)

Version: **1.0.0** (canon 2.5.0)

Subagent workflow for large product repos: **explore → plan → implement → verify**, with isolated child contexts and file-based handoff. The orchestrator (the main agent) is the single point of control — it decides delegation and owns the loop. This is deliberate: a flat "bag of agents" amplifies errors; a centralized orchestrator with a verification gate suppresses them.

---

## Agents

| Agent | Role | Writes | `model` (frontmatter) |
|-------|------|--------|------------------------|
| `code-explorer` | Read-only search + impact analysis | — | `inherit` |
| `task-planner` | Read-only decomposition into atomic steps | plan file | `inherit` |
| `implementer` | One plan step per invocation | code/tests | `inherit` |
| `verifier` | Read-only skeptic: confirms work is real | — | `inherit` |
| `doc-librarian` | Doc edits (via `maintain-docs`) | docs | `inherit` |

Dev agents are materialized only in **large product repos** (`cursor_agents_dev` in `normalize.bundle.yaml`). `doc-librarian` is materialized everywhere.

A repo is large enough to warrant the pipeline when it has **multiple packages/projects or a test suite worth isolating, and tasks routinely span several files**. Small or single-purpose repos skip it and let the orchestrator edit directly. Borderline: ask.

Subagents use **`model: inherit`** per [Cursor docs](https://cursor.com/docs/subagents.md) — they run on the parent agent's model. Tier guidance for when to delegate heavy work: `model-selection.md`.

---

## Orchestrator responsibilities

The main agent, not a subagent:

1. **Triage** — small known edits are done directly; multi-file work is delegated.
2. **Delegate** by the map in `docs/agent-map.md`, passing scope and `.tasks/` paths, not full file contents.
3. **Review the plan** before dispatching the implementer — the linear chain trusts each prior artifact, so a bad plan is caught here, not after implementation.
4. **Own the fix loop** — on `verifier: partial | fail`, send the Fix list back to the implementer for the named steps. Cap at **3 rounds**; beyond that, surface to the user rather than looping.

There is no orchestrator subagent and no "monitor" agent — in a sequential, human-in-the-loop session the user is the monitor.

---

## `.tasks/` handoff

Intermediate artifacts between subagents, passed by path:

```
.tasks/YYYY-MM-DD_<topic>_analysis.md   # code-explorer
.tasks/YYYY-MM-DD_<topic>_plan.md       # task-planner
.tasks/YYYY-MM-DD_<topic>_review.md     # verifier
```

`.tasks/` is in `.gitignore` (like `plans/`, `scratch/`). The parent passes **paths**, never pastes full contents into the chat.

---

## Context discipline

- Subagent `description` ≤ 2 lines (routing only); body short (link to `docs/agent-map.md`, no embedded canons).
- Full `docs/canons/` is read on normalize or dispute, not in normal dev.
- Built-in Explore / Bash handle tiny queries — `code-explorer` is for real impact analysis.

---

## Flow

```
orchestrator triage
  → code-explorer (scope)        → analysis.md
  → task-planner (analysis)      → plan.md
  → orchestrator reviews plan
  → implementer (one step) × N   → code
  → verifier (claim + plan)      → review.md
  → orchestrator: pass ⇒ close · partial/fail ⇒ fix loop (≤3)
```

Entry point and per-repo map: `docs/agent-map.md`.
