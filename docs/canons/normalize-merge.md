# Merge policy for normalization

Version: **2.3.0** (canon 2.4.0)

Normalization is **merge** with an existing repository, not replacement. The agent follows canon and role checklist while preserving project value.

See `normalize-governance.md`, `normalize.bundle.yaml`, `<WI>/normalize.deprecations.yaml`.

---

## Principles

1. Add and update what canon requires. Do **not** delete arbitrary project files — except paths in `normalize.deprecations.yaml` for versions being applied.
2. Respect project context: product code, docs, and dependencies stay meaningful for this repo.
3. `protocol-ref/` appears on protocol reconcile (group-sync), not on first normalize.

---

## Removing obsolete artifacts (required)

File **`<WORKSPACE_IMPROVE>/normalize.deprecations.yaml`** — versioned registry of paths to delete.

On normalize to `canon_version` **N**:

1. Read local `canon_version` (`group.manifest.yaml` → `group.canon_version` or last entry in `docs/normalize-record.md`).
2. For each `deprecations` block with version **V** where `local < V <= N`, delete listed paths for repo role (`all` + `head` | `subordinate` | `standalone`).
3. Skill directory path (`.cursor/skills/<name>`) — delete **entirely**.
4. Files with `project-local:` marker — do **not** touch, even if path matched (must not be in deprecations).
5. In normalize report — section **Removed (deprecations)** with actually deleted paths; missing ones — "(already absent)".

On each WI release with new `canon_version`, **append** a new block — do not edit old blocks retroactively.

---

## `project-local:` marker

At file start — signal that file is outside normalization scope and **outside** deprecations:

```markdown
<!-- project-local: -->
```

Also excludes the file from language migration (agent-cache translation).

---

## Language migration merge

Translation on re-normalize is **merge**, not blind replace:

- Preserve project facts: module names, paths, `sub-id`, technical identifiers.
- Change prose language to English for agent-cache tier paths.
- Do not translate files with `project-local:`.
- Do not touch human-tier (`CHANGELOG`, `OPERATOR-HANDOFF`) or `src/` UI strings.

---

## Re-updating canons

Agent pulls current `docs/canons/` from WI into local copy (English source) and applies deprecations per rules above.
