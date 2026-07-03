# Canon: normalization

Version: **1.7.0** (canon 2.5.0)

Normalization brings a repository to the **role structure** (S / H / Sub) per Workspace improve canons.

Performed by the **target repository agent** (initiator or skill `normalize-project`). WI is the source of canons and templates; no edits to other repos from WI.

---

## Procedure

1. Confirm role **S | H | Sub** and path to WI (`WORKSPACE_IMPROVE`).
2. Read canons **by role** (not the entire catalog):
   - **S:** `normalize-governance.md`, `project-structure.md`, `normalize-merge.md`, `documentation.md`
   - **H / Sub:** same + `group-sync.md`
   - **Large product repos:** add `dev-pipeline.md` (subagent workflow)
3. Target-state checklist: `<WI>/normalize.bundle.yaml`.
4. **Deprecations (obsolete paths):** remove the fully-obsolete paths in `<WI>/normalize.deprecations.yaml` (inbox/outbox, packet templates, legacy skills). **Defer** any deprecated file whose content still matters (e.g. `agent-onboarding.md`) — it is removed in step 7, after its successor exists (see *Deprecations with surviving content*).
5. Bring repo to checklist: docs, `docs/canons/`, `.cursor/`, scripts by role — respecting what already exists. Utilities are **canon-coupled**: on a canon bump, overwrite `scripts/*.py` from `<WI>/scripts/` (they encode the current layout — e.g. hub vs inbox/outbox — and are not project code).
6. Templates from `<WI>/templates/` (read and materialize, not a full mirror).
7. **Documentation:** materialize successors and align entry-point docs via **`maintain-docs`** → **`doc-librarian`**; fold surviving content from any deferred deprecated file into its successor, then remove that file. No bulk doc edits in the parent chat.
8. **Language** (legacy non-English repos only — see *Language policy* below).
9. `docs/normalize-record.md`, `project-doctor`, report (including removed deprecations section).

When ambiguous — ask.

---

## Deprecations with surviving content

A deprecated file is not always fully dead — `agent-onboarding.md` is removed in 2.5, but its project-specific operational policies live on. Migrate before deleting:

1. `doc-librarian` folds orchestration-relevant content into the successor entry (`docs/agent-map.md`, ≤ ~80 lines); deep product policy goes to `architecture.md` or a dedicated on-demand doc.
2. Only then apply the deprecation removal.

Order matters: a deprecation runs as a delete, so removing first loses the content.

---

## Group normalize ordering

Normalize the **Head first** — it creates `GROUP-HUB.md`, which every Sub's `sync` skill targets at `<head.path>/GROUP-HUB.md`. Then the Subs. Cut a live group over only when it is `stable`; full procedure in `group-sync.md` → *Migrating 2.4 → 2.5*.

---

## Language policy

Agent-facing docs are authored in **English** (cached every session; one language keeps the cache tight). New repos start English.

**Legacy fallback:** if a repo's agent-cache docs are in another language (`agent_docs_lang != en` in `docs/normalize-record.md`), delegate a one-time translation to **`doc-librarian`** — agent-cache tier paths only, as a merge — then set `agent_docs_lang: en`.

---

## Materializing `.cursor/`

Skills and agents per role list in `normalize.bundle.yaml`. Adapt to repo: module id, head paths, local links.

Copy agents **only** from `<WI>/templates/agents/<name>.md` → `.cursor/agents/<name>.md` (full file). Use the templates, not stub files from WI `.cursor/agents/`.

`doc-librarian` is materialized in every repo. The dev-pipeline agents (`code-explorer`, `task-planner`, `implementer`, `verifier`) go only into large product repos, per `cursor_agents_dev` in `normalize.bundle.yaml`.

Remove deprecated skills/agents from deprecations **before** copying new templates.

Project-local Cursor features — `.cursor/commands/` and any repo-specific `.cursor/rules/` — are left untouched. WI's optional convention rules live in `templates/cursor-rules/` (install when wanted).

---

## When new tooling becomes active

Cursor loads agents, skills, and rules at **session start** — freshly materialized `.cursor/` files are not guaranteed to be live in the same run that writes them. So the normalize run is designed **not to depend** on the new tooling being active:

- It is driven by the already-loaded `normalize-project` skill / initiator, not by the agents it installs.
- The doc-alignment step delegates to `doc-librarian` when it is available; if the new librarian is not yet live, the orchestrator does the doc edits inline this once (context isolation is an optimization here, not a correctness requirement).
- The dev-pipeline agents are for later work, not used during normalize at all.

Run normalize in **one pass**, then start a **fresh session** for real work — where the new agents/skills/rules are loaded. No two-pass restart is required.

---

## Utilities (by role, in `scripts/`)

| Script | Purpose |
|--------|---------|
| `project-doctor.py` | Structure check |
| `protocol-snapshot.py` | Baseline / review-snapshot (H/Sub) |
| `sync-status.py` | Hub pending + registry (Head) / integration state (Sub) |

---

## Re-normalization

Same cycle: current WI canons → deprecations by version → update local copy in repo → language migration when needed.

---

## WI release: author duties

On bump of `canon_version` in `normalize.bundle.yaml`:

1. Add a block to `normalize.deprecations.yaml` for paths that must no longer exist in product repos.
2. Note removal in `CHANGELOG.md`.
3. Do not rely on "merge does not delete" — deprecations override that for listed paths.
