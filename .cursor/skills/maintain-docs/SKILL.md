---
name: maintain-docs
description: >-
  Delegate all documentation work to doc-librarian subagent. Use for docs updates,
  CHANGELOG, onboarding, architecture, group integration, language migration.
---

# Maintain docs

Invoke subagent **`doc-librarian`** for the current repository.

Pass: what to update, scope (files or task), role context if known.

Do not perform large doc edits in the parent chat.

For language migration on re-normalize, pass explicit scope from `agent_cache_tier` in `normalize.bundle.yaml`.
