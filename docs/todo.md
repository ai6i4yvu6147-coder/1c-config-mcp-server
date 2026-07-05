# Project backlog

Live list of open tasks and ideas for **1C configuration MCP server functionality** (parser, index, MCP tools, admin GUI). File in git — so after clone on another machine the current state is visible.

**Do not duplicate** closed tasks and history here — only what is not done yet. Closed items — in [`CHANGELOG.md`](../CHANGELOG.md).

**Do not include** operational steps (portable rebuild, manual `databases/*.db` recreation by user, MCP setup in IDE) — those are not tool improvements.

## Hub pending

(none — THR-008 resolved; Head registry shows `stable`, no active thread)

## Admin Hub / group integration

- **Status:** `stable`, epoch 0 (see [`group/integration.md`](group/integration.md))
- Admin Hub Phase 3 rebuild CLI — **done**; `operations.log` — **done**

## How to use

| Role | Action |
|------|--------|
| Project owner | Adds items, changes status, removes completed |
| Agent | On request reads the list, checks readiness for an item, suggests next step |

## Statuses

| Status | Meaning |
|--------|---------|
| `idea` | Intent, not yet shaped into a task |
| `ready` | Task formulated, can be taken |
| `blocked` | Waiting on external condition (export, scope decision) |
| `in-progress` | In progress |

When done, the item is **removed** from the list (or moved to CHANGELOG — by agreement).

## Readiness check (for agent)

On request "check todo" or "can we do X from the list":

1. Read this file.
2. For the relevant item — is there code/docs/tests in the repo; for parser — is a real export needed (see `agent-map.md`).
3. Answer: what is ready, what is missing, what blocks start.

Do not start implementation from the list without explicit user request.

---

## State snapshot (2026-06-29)

| Area | Status |
|------|--------|
| `ScheduledJob` in whitelist, `scheduled_jobs`, `used_in_scheduled_job` | **done** (see CHANGELOG) |
| Scheduled job search via `list_objects` / `find_object` / `get_object_structure` | **done** (by metadata name) |
| Object search by **synonym** (`metadata_objects.synonym`) | **done** (see CHANGELOG) |
| **`find_referencing_objects`** (reverse search by slots) | **done** (see CHANGELOG) |
| Scheduled job search by `MethodName` | **no** — see `scheduled-job-search` |
| Admin GUI: bulk update, operation status | **no** — see `gui-bulk-update` |
| Admin Hub protocol Phase 1 (manifest, read-only CLI) | **done** — see CHANGELOG, [`admin-hub-integration.md`](admin-hub-integration.md) |
| Admin Hub protocol Phase 2–3 (sync, rebuild CLI) | **done** (incl. `operations.log`); see `integration.md` |
| Admin GUI: build stage log / timings | **no** — see `gui-build-log-timings` |
| Whitelist extension (Role, EventSubscription, …) | **partial** — `Subsystem` done (phase 3); see `dependency-layer.md` phases 4–5 |
| Type system (metadata + forms, `metadata_type_slots`) | **done** — v8–9; current index format — `INDEXER_VERSION` 10; see CHANGELOG, [`form-type-system.md`](form-type-system.md) |
| `metadata_relations` (subsystems, roles, …) | **partial** — subsystems (phase 3, v10); roles/subscriptions — phases 4–5 |

---

## Tasks

<!-- id | status | brief | context / links -->

- **form-dynamiclist-settings** · `idea` · Parse DynamicList Settings on form (MainTable, DCS)

  - **Why:** currently DynamicList in v1 — wrapper + `query_text` only; agent does not see main table/data source from Settings

  - **Scope (draft):** `Settings/MainTable`, link to metadata object; optional DCS fields — refine against reference Form.xml (Scheduler, ARM)

  - **Related:** [`form-type-system.md`](form-type-system.md) (basic form type system **done**); may require bump `INDEXER_VERSION` and new DB fields

  - **Not in current iteration** — separate backlog item after v10

- **gui-bulk-update** · `ready` · Bulk update all configurations + progress indicator

  - **Task:** update all databases of all projects (or selected project) in one command, with saved `source_xml` paths

  - **UI (minimum):** status line/header, e.g. "Updating project Hamburg, extension FT_Dorabotki"; progress (N of M) if possible

  - **Side:** `admin_tool/gui_v2.py`, `ProjectManager` (XML paths already in `projects.json`)

  - **Open:** stop on first error; update only stale or all

  - **Done when:** one button/action walks databases with `source_xml`; user sees current operation; tree is up to date on completion

- **scheduled-job-search** · `idea` · Scheduled job search by `MethodName`

  - **Problem:** procedure from `MethodName` (`CommonModule.X.Y`) is not found via `find_object`

  - **Options:** extend `find_object` for ScheduledJob type · JOIN with `scheduled_jobs.method_name` · separate MCP tool

  - **Materials:** `scheduled_jobs` table; on schema change — `bump-indexer-version.mdc`

  - **Not to confuse with** dependency layer (`dependency-layer.md`) — separate axis (handler, not metadata ref)

  - **Done when:** query "find scheduled job for procedure Y" returns relevant result

- **relations-phase-4** · `blocked` · whitelist `Role` (MVP grants)

  - **Spec:** [`dependency-layer.md`](dependency-layer.md) — phase 4; **blocked** without real role export

- **relations-phase-5** · `blocked` · `EventSubscription`

  - **Spec:** [`dependency-layer.md`](dependency-layer.md) — phase 5; **blocked** without real export

---

## Ideas

<!-- status: idea — no fixed scope -->

- **gui-build-log-timings** · `idea` · DB build stage log and timings on update form

  - **Task:** on create/update DB form — scrollable list (like a log): lines as stages complete, with duration, e.g. `12:01:05 — XML parse — 412 s`, `12:07:12 — Objects (N) — …`, `12:14:03 — Forms — …`, `12:14:10 — fo_content_ref / scheduled job linking — 0.4 s`, `Done`

  - **Why:** on large exports (Logist main) unclear if "hung" or long stage; timings show bottlenecks (parser vs forms vs other)

  - **Side:** `admin_tool/db_manager.py` (stage breakdown + `time.perf_counter()`), `admin_tool/gui_v2.py` (log widget)

  - **Why progress bar failed before (account for in implementation):**
    - `DatabaseManager.create_database` already accepts `progress_callback`, but **GUI does not pass it** — all threads call `create_database(xml)` without callback (`CreateDatabaseWindow`, `QuickUpdateDialog`, `UpdateDatabaseWindow`)
    - update runs in **background `threading.Thread`**; in tkinter **cannot** touch widgets from worker thread — only via `queue.Queue` + `root.after()` (or `after` with queue polling)
    - current callbacks in `_insert_configuration` — only "Objects" / "Forms" every 10 objects; **no** messages for XML parse, `fo_content_ref`, `_link_scheduled_job_procedures`, commit — UI "silent" for minutes

  - **Recommended MVP (simpler than progress bar):** append-only `ScrolledText` / `Listbox` + event queue; do not try smooth `%` first — discrete lines on **stage completion** enough. Progress bar — optional later if same `after` mechanism works

  - **tkinter constraint:** dynamic updates **possible**, but only with correct thread → queue → main loop; otherwise UI looks "dead". If `after` queue unreliable on long builds — document in item and consider UI alternative (`gui-redesign`)

  - **Related:** `gui-bulk-update` (same log on bulk update)

  - **Done when:** on Logist main update log shows all major stages with seconds; UI updates during build without freezing

- **gui-cancel-build** · `idea` · Cancel DB load/update from GUI

  - **Task:** "Cancel" on create/update DB form — stop long build without closing entire admin tool

  - **Why:** on large configs (10–20+ min) user may pick wrong file, wrong database, or change mind; thread runs to end, window "silent"

  - **Side:** `admin_tool/gui_v2.py` (button, cancel flag, thread state), `admin_tool/db_manager.py` (cancel checks in long loops)

  - **Technically (account for):**
    - `threading.Thread` **cannot** be reliably killed externally — cooperative cancel: `threading.Event` / `should_cancel()` callback → checks in `_insert_configuration` (object/form loops), optionally in parser
    - full XML parse (`parser.parse()`) **not interruptible** mid-way currently — accept "cancel after parse" or staged parse (separate work)
    - on cancel: `rollback` / no `commit`, remove or do not leave broken `.db` (file often `unlink()` before build — document desired behavior)
    - UI: button active only during build; on cancel — log entry (`gui-build-log-timings`) "Cancelled by user"

  - **Related:** `gui-build-log-timings`, `gui-bulk-update` (cancel one DB in batch / cancel whole batch — clarify)

  - **Done when:** during build "Cancel" stops process in reasonable time (seconds, not minutes); no "half-ready" working DB left in `projects.json`/tree without explicit warning

- **gui-redesign** · `idea` · Refresh admin GUI look (optional)

  - **Context:** currently tkinter "utilitarian", like old software; improve readability, spacing, icons/colors, maybe `ttk` theme

  - **Side:** `admin_tool/gui_v2.py`

  - **Priority:** low; does not block `gui-bulk-update` and status fix

  - **Open:** stay on tkinter or consider another UI layer

- **whitelist-role** · `idea` · Index roles (`Role`)

  - **Why:** `role_grant` in `metadata_relations`, rights analysis

  - **Materials:** whitelist, [`dependency-layer.md`](dependency-layer.md) phase 4; **blocked** without real role export

  - **Open:** MVP without full RLS model (rights in `source_path`)

- **whitelist-event-subscription** · `idea` · Index event subscriptions (`EventSubscription`)

  - **Why:** `event_source` / `event_handler` in `metadata_relations`

  - **Materials:** whitelist, [`dependency-layer.md`](dependency-layer.md) phase 5; **blocked** without real export

  - **Open:** reverse index handler → subscriptions

- **whitelist-http-service** · `idea` · Index HTTP services (`HTTPService`)

  - **Low priority** among whitelist candidates; refine on request
