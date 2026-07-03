---
name: normalize-project
description: >-
  Normalize this repository (S/H/Sub) per WI canon and role checklist.
disable-model-invocation: true
---

# Normalize project

Role: **S** | **H** | **Sub** (confirm if not specified).

WI path: `WORKSPACE_IMPROVE`.

## Procedure

1. Canons by role:
   - **S:** `normalize-governance.md`, `project-structure.md`, `normalize-merge.md`, `documentation.md`
   - **H / Sub:** same + `group-sync.md`
   - **Large product repo:** also `dev-pipeline.md` (+ `cursor_agents_dev` agents)
2. Checklist: `<WI>/normalize.bundle.yaml` for selected role.
3. **Deprecations** (required on re-normalize):
   - Read `<WI>/normalize.deprecations.yaml`.
   - Local `canon_version` — from `group.manifest.yaml` or `docs/normalize-record.md`.
   - Target — `canon_version` from bundle.
   - Remove paths from blocks where `local < V <= target`, for `all` + repo role.
   - `.cursor/skills/<name>` directories — remove entirely.
   - Content-bearing files (e.g. `agent-onboarding.md`) — salvage into successors via `doc-librarian` **before** removing.
   - **Group:** normalize Head before Subs; migrate packet→hub per `group-sync.md`.
   - Report section **Removed (deprecations)** — removed / already absent.
4. Bring repo to checklist; templates from `<WI>/templates/`. Agents — full copies from `templates/agents/*.md`.
5. Copy `docs/canons/` from WI (English source).
6. Docs to canon: skill **`maintain-docs`** → **`doc-librarian`** (no bulk edits in parent chat).
7. **Language (legacy only):** if `agent_docs_lang != en`, delegate a one-time translation of agent-cache paths to **`doc-librarian`**, then set `agent_docs_lang: en`. English repos — skip.
8. `docs/normalize-record.md`, `project-doctor`, report.
