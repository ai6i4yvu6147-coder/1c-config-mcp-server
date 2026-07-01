# Canon: normalization

Version: **1.5.0** (canon 2.4.0)

Normalization brings a repository to the **role structure** (S / H / Sub) per Workspace improve canons.

Performed by the **target repository agent** (initiator or skill `normalize-project`). WI is the source of canons and templates; no edits to other repos from WI.

---

## Procedure

1. Confirm role **S | H | Sub** and path to WI (`WORKSPACE_IMPROVE`).
2. Read canons **by role** (not the entire catalog):
   - **S:** `normalize-governance.md`, `project-structure.md`, `normalize-merge.md`, `documentation.md`
   - **H / Sub:** same + `group-sync.md`
3. Target-state checklist: `<WI>/normalize.bundle.yaml`.
4. **Deprecations:** `<WI>/normalize.deprecations.yaml` — remove obsolete paths (see `normalize-merge.md`).
5. Bring repo to checklist: docs, `docs/canons/`, `.cursor/`, scripts by role — respecting what already exists.
6. Templates from `<WI>/templates/` (read and materialize, not a full mirror).
7. **Documentation:** align entry-point docs via skill **`maintain-docs`** → subagent **`doc-librarian`**. No bulk doc edits in the parent chat.
8. **Language migration** (re-normalize, when applicable — see below).
9. `docs/normalize-record.md`, `project-doctor`, report (including removed deprecations section).

When ambiguous — ask.

---

## Language migration (re-normalize)

After materializing `.cursor/` and copying `docs/canons/` from WI (already English):

1. Read `agent_docs_lang` from `docs/normalize-record.md` (missing = legacy `ru`).
2. If upgrading to `canon_version` **≥ 2.4.0** or `agent_docs_lang != en` → skill **`maintain-docs`** with task:

   *Translate all agent-cache tier paths to English per `documentation.md`; preserve project-local markers; do not touch CHANGELOG, OPERATOR-HANDOFF, or `src/` UI strings.*

3. After success, set `agent_docs_lang: en` in `docs/normalize-record.md`.

Delegate to **`doc-librarian`** — no bulk translation in the parent normalize chat.

---

## Materializing `.cursor/`

Skills and agents per role list in `normalize.bundle.yaml`. Adapt to repo: module id, head paths, local links.

Copy agents **only** from `<WI>/templates/agents/<name>.md` → `.cursor/agents/<name>.md` (full file). Do not use stub files from WI `.cursor/agents/`.

Remove deprecated skills/agents from deprecations **before** copying new templates.

---

## Utilities (by role, in `scripts/`)

| Script | Purpose |
|--------|---------|
| `project-doctor.py` | Structure check |
| `protocol-snapshot.py` | Baseline / review-snapshot (H/Sub) |
| `sync-status.py` | State summary; `--operator-check` |

---

## Re-normalization

Same cycle: current WI canons → deprecations by version → update local copy in repo → language migration when needed.

---

## WI release: author duties

On bump of `canon_version` in `normalize.bundle.yaml`:

1. Add a block to `normalize.deprecations.yaml` for paths that must no longer exist in product repos.
2. Note removal in `CHANGELOG.md`.
3. Do not rely on "merge does not delete" — deprecations override that for listed paths.
