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
2. Checklist: `<WI>/normalize.bundle.yaml` for selected role.
3. **Deprecations** (required on re-normalize):
   - Read `<WI>/normalize.deprecations.yaml`.
   - Local `canon_version` — from `group.manifest.yaml` or `docs/normalize-record.md`.
   - Target — `canon_version` from bundle.
   - Remove paths from blocks where `local < V <= target`, for `all` + repo role.
   - `.cursor/skills/<name>` directories — remove entirely.
   - Report section **Removed (deprecations)** — removed / already absent.
4. Bring repo to checklist; templates from `<WI>/templates/`. Agents — full copies from `templates/agents/*.md`.
5. Copy `docs/canons/` from WI (English source).
6. Docs to canon: skill **`maintain-docs`** → **`doc-librarian`** (no bulk edits in parent chat).
7. **Language migration** (when `canon_version` ≥ 2.4.0 or `agent_docs_lang != en`):
   - skill **`maintain-docs`** → **`doc-librarian`**: translate all `agent_cache_tier` paths per `documentation.md`; skip `project-local:`, CHANGELOG, OPERATOR-HANDOFF, `src/` UI.
   - Set `agent_docs_lang: en` in `docs/normalize-record.md`.
8. `docs/normalize-record.md`, `project-doctor`, report.
