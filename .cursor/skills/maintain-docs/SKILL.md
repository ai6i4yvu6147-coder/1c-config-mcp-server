---
name: maintain-docs
description: >-
  Delegate documentation work to the doc-librarian subagent: docs updates,
  CHANGELOG, onboarding, architecture, group integration, language migration.
---

# Maintain docs

Invoke subagent **`doc-librarian`** for the current repository. Pass what to update, the scope (files or task), and role context if known — the librarian keeps bulk doc work in its own context and returns a compact report.

For language migration on re-normalize, pass explicit scope from `agent_cache_tier` in `normalize.bundle.yaml`.
