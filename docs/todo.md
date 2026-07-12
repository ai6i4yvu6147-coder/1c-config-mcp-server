# Project backlog

Live list of open tasks and ideas for **1C configuration MCP server functionality** (parser, index, MCP tools, admin GUI). File in git — so after clone on another machine the current state is visible.

**Do not duplicate** closed tasks and history here — only what is not done yet. Closed items — in [`CHANGELOG.md`](../CHANGELOG.md).

**Do not include** operational steps (portable rebuild, manual `databases/*.db` recreation by user, MCP setup in IDE) — those are not tool improvements.

## Hub pending

## Admin Hub / group integration

- **Status:** `stable` (`sync_state`; see [`group/integration.md`](group/integration.md))
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
| Admin GUI: build stage log / timings | **done** — validated on real exports and live in the rebuilt admin GUI; see `gui-build-log-timings` |
| Whitelist extension (Role, EventSubscription, …) | **partial** — `Subsystem` (phase 3), `Role` (phase 4); see `dependency-layer.md` phase 5 |
| Type system (metadata + forms, `metadata_type_slots`) | **done** — v8–16; current index format — `INDEXER_VERSION` 16; see CHANGELOG, [`form-type-system.md`](form-type-system.md) |
| `metadata_relations` / role grants | **done** — subsystems (phase 3); roles via `role_grants` (phase 4); role UX polish (layer naming, merge, relation_kinds) — see CHANGELOG 2026-07-08 |

---

## Tasks

<!-- id | status | brief | context / links -->

- **external-processor-root** · `ready` · External data processor as third project-root kind (Variant B)

  - **Why:** today `parse()` only accepts `Configuration` root; external processors (`MetaDataObject/ExternalDataProcessor` in `<Name>.xml`) are invisible — **not** a whitelist entry (see [`metadata-whitelist.md`](metadata-whitelist.md))

  - **Canon:** Head `docs/group/shared/metadata-library-cluster.md`; library `C:/projects/1c-metadata-schema` (`onec_metadata_schema.parse()` → generic `Node`)

  - **Approach:** root dispatch in `shared/xml_parser/core.py` → `onec_metadata_schema.parse()` → adapter `Node → dict` matching `_parse_object(..., obj_type='DataProcessor')` → existing `insert_objects.py` pipeline unchanged

  - **Recon first:** (1) dict shape from `_parse_object` for embedded `DataProcessor`; (2) which `_insert_*` paths apply for a single-object “configuration”

  - **Also:** `project_manager.py` `source_xml` may need to accept external processor file path; verify form EAV compatibility with adapter output

  - **Verify:** real MCP tool calls per [`testing-protocol.md`](testing-protocol.md) — not Configurator load (that is library criterion)

  - **Docs on completion:** `architecture.md`, `mcp-tools.md`, `metadata-whitelist.md`

  - **Not in this track:** full whitelist migration (Stage G in metadata-schema); other 14+ types stay on current parser

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

- **relations-phase-5** · `blocked` · `EventSubscription`

  - **Spec:** [`dependency-layer.md`](dependency-layer.md) — phase 5; **blocked** without real export

---

## Ideas

<!-- status: idea — no fixed scope -->

- **gui-build-log-timings** · `done` · DB build stage log and timings on update form

  - **Task:** on create/update DB form — scrollable list (like a log): lines as stages complete, with duration, e.g. `12:01:05 — XML parse — 412 s`, `12:07:12 — Objects (N) — …`, `12:14:03 — Forms — …`, `12:14:10 — fo_content_ref / scheduled job linking — 0.4 s`, `Done`

  - **Why:** on large exports (Logist main) unclear if "hung" or long stage; timings show bottlenecks (parser vs forms vs other)

  - **Done (2026-07-05):**
    - `admin_tool/db_manager/core.py` + `insert_objects.py` — stage boundaries (parse, schema, objects, relations/fo_content_ref/scheduled-job linking, forms, done) timed via `time.perf_counter()`, folded into the existing `progress_callback(current, total, message)` messages — no signature/return-type changes
    - `shared/xml_parser/core.py` — finer per-stage breakdown *within* XML parse itself (modules/forms/properties/sections/flowchart/commands/subsystems), via `self.stage_seconds` + `_accumulate()` context manager; surfaced as an indented breakdown under the "XML parse" line
    - `admin_tool/gui_v2.py` — `AddDatabaseWindow`, `QuickUpdateDialog`, `UpdateDatabaseWindow` now pass a `progress_callback` into `build_from_xml_atomic` (previously omitted entirely — the actual root cause of "UI silent for minutes"); each dialog got a small `ScrolledText` log widget, appended via the existing `AdminAppV2.schedule_on_main()` (`root.after(0, fn)`) — no queue needed, per-stage call volume is low
    - `scripts/parse-benchmark.py` (new) — standalone CLI to run the parser/builder against a real export outside the GUI/exe, for timing measurement without touching `projects.json`/`databases/`
    - **Validated against real exports:** Фитэра/Задачник (631 MB, 2151 objects, 11.4 s) and АСБ/Бухгалтерия (5.8 GB, 11114 objects, 148.5 s) — both parse+build cleanly end to end
    - **Bug found + fixed along the way:** Windows `MAX_PATH` (260 char) silently broke/crashed on the АСБ export's deeply nested Subsystems tree (a 261-char path) — `ET.parse()`/`.exists()`/`open()` across the whole `shared/xml_parser/` package now go through a `_winlong()` (`\\?\` extended-length prefix) helper in `xml_helpers.py`. Also fixed a console-encoding crash in the benchmark script itself (a box-drawing character wasn't encodable in the Windows console codepage)
    - **Validated live in the rebuilt admin GUI** (user-confirmed): log widget shows real stage progress during an actual update
    - **Follow-up fix:** live use showed the per-10-objects/forms counters ("Объекты N/M") flooding the log with hundreds of lines — `progress_callback` gained an optional `replace_last` flag; those recurring counters now update the same log line in place (Tk Text last-line delete range is `'end-2l'..'end-1l'`, not `'end-1l'..'end'` — Tk always keeps one extra trailing blank row) while stage-boundary summaries stay as separate permanent lines

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

- **whitelist-event-subscription** · `idea` · Index event subscriptions (`EventSubscription`)

  - **Why:** `event_source` / `event_handler` in `metadata_relations`

  - **Materials:** whitelist, [`dependency-layer.md`](dependency-layer.md) phase 5; **blocked** without real export

  - **Open:** reverse index handler → subscriptions

- **whitelist-http-service** · `idea` · Index HTTP services (`HTTPService`)

  - **Low priority** among whitelist candidates; refine on request
