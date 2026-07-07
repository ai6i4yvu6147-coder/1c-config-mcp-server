# Roles and access restrictions (phase 4)

**Status:** phase 4 spec (implementation not started)

Task-oriented parsing and MCP tools for 1C roles and row-level security (RLS). Parsing exists to support agent workflows, not for its own sake.

Parent roadmap: [`dependency-layer.md`](dependency-layer.md) phase 4. Reference export (validated): `Фитэра/АСБ тест` — main `Основная конфигурация` + extension `ФТ_Бюджетирование`.

---

## Agent use cases (from product brief)

| # | Need | Owner |
|---|------|-------|
| 1 | Find role by name / synonym | config-mcp |
| 2 | Role → objects, right types, RLS presence | config-mcp |
| 3 | **Merged** effective role (main + extension(s)); also per-layer view | config-mcp |
| 4 | Access profile structure (for runtime analysis) | data-mcp (uses config schema) |
| 5 | Profile summary / comparison | data-mcp |
| 6 | Access groups | data-mcp |
| 7 | “Why can user X see document Y?” | config-mcp + data-mcp |
| 8 | “Role gives Read without RLS — add RLS or switch profile?” | config-mcp + data-mcp |

Profiles and access groups (`Catalog.ПрофилиГруппДоступа`, `Catalog.ГруппыДоступа`) are **runtime** data. Config-mcp stores role rights and restriction **definitions**; data-mcp resolves users → profiles → groups → role identifiers.

---

## config-mcp vs data-mcp

### config-mcp

- Role metadata, `Rights.xml` grants, access restrictions, restriction templates
- Merge effective role across layers (main + extensions)
- Reverse lookup: which roles grant a right on an object

### data-mcp (contract; tools TBD)

**Agreed:** contract stays in this doc until data-mcp implementation; separate protocol addendum when tools ship in the data-mcp repo.

- `get_user_access_chain` — user → access groups → profiles → roles (`role_qualified_name`)
- `find_profiles_by_role` — profiles containing a role
- `get_profile_access` — profile roles + access kinds / values (ТЧ `ВидыДоступа`, `ЗначенияДоступа`)

### Link key (config ↔ data)

Profile tabular section `Роли.Роль` → `Catalog.ИдентификаторыОбъектовМетаданных` or `Catalog.ИдентификаторыОбъектовРасширений` → field **`ПолноеИмя`** = `Role.<RoleName>`.

```json
{
  "role_qualified_name": "Role.ЧтениеРеализацииТоваровУслуг",
  "role_name": "ЧтениеРеализацииТоваровУслуг",
  "role_uuid": "<from Role.xml>",
  "source_layer": "main | <extension_name>",
  "extension_name": null
}
```

For adopted extension roles: extension `Role.xml` has its own `uuid` and `ExtendedConfigurationObject` pointing at the main role uuid.

**Adopted identity (agreed):** merge and lookup by role **`Name`**. API also returns `extended_configuration_object_uuid` when `ObjectBelonging=Adopted` (link to main role uuid).

---

## XML sources

| File | Content |
|------|---------|
| `Roles/<Name>.xml` | Role metadata: `Name`, `Synonym`, `uuid`; extension: `ObjectBelonging`, `ExtendedConfigurationObject` |
| `Roles/<Name>/Ext/Rights.xml` | Grants, restrictions, templates, role flags |

### Role flags (root of `Rights.xml`)

| XML | Configurator label |
|-----|-------------------|
| `setForNewObjects` | Set rights for new objects |
| `setForAttributesByDefault` | Set rights for attributes and tabular sections by default |
| `independentRightsOfChildObjects` | Independent rights of child objects |

### Grants (`<object>` + `<right>`)

- Target: qualified name (`Document.X`, `Document.X.Attribute.Y`, `Report.X.TabularSection.TS.Attribute.A`, …)
- `right/name` + `right/value` (`true` / `false`)
- Field-level entries are **grants** (e.g. `Edit=false` on attributes when `setForAttributesByDefault=true`)

### Access restrictions (UI: “Ограничения доступа к данным”)

Not stored inside `role_grants`. One UI table row = one `<restrictionByCondition>` under a `<right>`:

| UI “Поля” | XML |
|-----------|-----|
| `<Прочие поля>` | `<restrictionByCondition>` **without** `<field>` |
| Specific field (e.g. `Ref`, `ВерсияОбъекта`) | `<restrictionByCondition><field>…</field><condition>…</condition>` |

**Multiple** `<restrictionByCondition>` siblings under the **same** `<right>` are valid (verified in extension export).

`restriction_text` = content of `<condition>` (may be template macros `#ПоЗначениям`, `#ДляОбъекта`, or query language e.g. `БанковскиеСчета ГДЕ …`).

Pairs inside `#ПоЗначениям("…", "Организации", "Организация", …)` are **parameters of one restriction** for “прочие поля”, not separate UI rows. Do not split into separate restriction rows.

**MVP:** store `restriction_text` verbatim only. At tool response time, optional `restriction_kind` via prefix (`by_values` | `for_object` | `query` | `unknown`) — no parsing of `#ПоЗначениям` pairs. Tier 3: `access_kind_hints` for data-mcp.

### Restriction templates

`<restrictionTemplate>` at end of `Rights.xml` (role tab “Шаблоны ограничений”): `name` + `condition` body. Referenced from restriction `condition` text.

---

## Data model (SQLite)

Separate tables; bump `INDEXER_VERSION` when implemented.

### `role_settings` (per role per layer)

`role_object_id`, `set_for_new_objects`, `set_for_attributes_by_default`, `independent_rights_of_child_objects`, `source_db_name`.

### `role_grants`

| Column | Notes |
|--------|-------|
| `role_object_id` | FK `metadata_objects` (`Role`) |
| `target_qname` | As in `Rights.xml` `<object><name>` |
| `target_kind` | `object` \| `attribute` \| `resource` \| … |
| `parent_object_qname` | For field-level rows |
| `right_name` | `Read`, `View`, `Edit`, … |
| `granted` | bool |
| `source_db_name` | Main or extension db name |

### `role_access_restrictions`

| Column | Notes |
|--------|-------|
| `grant_id` | FK → `role_grants` (object-level right, `granted=true`) |
| `field_scope` | `NULL` = “прочие поля”; else field name (`Ref`, `ВерсияОбъекта`, …) |
| `restriction_text` | `<condition>` verbatim |
| `source_db_name` | |

One grant : N restrictions (0..N).

### `role_restriction_templates`

`role_object_id`, `template_name`, `condition_text`, `source_db_name`.

### Reverse lookup (phase 4)

**Agreed:** `find_roles_for_object` and `find_referencing_objects` (`via: role_grant`) query **`role_grants`** directly (JOIN on parent object qname). Do **not** materialize `metadata_relations.role_grant` in phase 4 — avoids duplicate data (~17k+ object rows). Revisit denormalized index only if profiling requires it.

---

## Merge semantics

**Agreed.** Effective role state (`get_role_rights` with `merge=true`) simulates platform composition: main configuration plus all extension databases of the infobase (same `project_filter`, no `extension_filter`).

Per-layer view (`merge=false`) returns **only** what that layer’s export contains — **no inheritance** from main, even for adopted roles.

### Role kinds

| Kind | Main | Extension | `merge=true` starting point |
|------|------|-----------|----------------------------|
| Main-only | `Rights.xml` | — | main |
| Extension-new | — | full `Rights.xml` | empty, then extension layers |
| Adopted | full `Rights.xml` | delta or no file | main, then extension overlays |

Adopted role without extension `Rights.xml`: that extension layer contributes nothing; effective state still includes main and other extensions.

### Extension layer priority

Extensions are applied **after** main, sorted by `ConfigurationExtensionPurpose` in extension `Configuration.xml` (ascending priority; **later wins** on key conflict):

| XML value | Configurator label | Priority |
|-----------|-------------------|----------|
| `Customization` | Доработка | lowest |
| `AddOn` | Адаптация | middle |
| `Patch` | Исправление | highest |

Within the same purpose: stable tie-break by `source_db_name` (alphabetical) until explicit platform order is indexed.

Indexer must persist `extension_purpose` per extension database (from `Configuration.xml`); expose in `active_databases` for agents.

### Overlay rules (all entity types)

Walk layers in priority order. When a layer defines a key, it **replaces** the accumulated value.

| Entity | Conflict key |
|--------|----------------|
| Grants | `(target_qname, right_name)` |
| Access restrictions | `(target_qname, right_name, field_scope)` — `field_scope = NULL` = «прочие поля» |
| Role settings (3 flags) | whole role: if layer has `Rights.xml` for this role, root flags from that file replace previous effective flags |
| Restriction templates | `template_name` |

Grants: extension may set `granted=false` and override main `true` for the same key.

Restrictions: **replace by field key**, not union. Two restrictions on one right (e.g. прочие поля + `Ref`) are distinct keys and both survive unless the same key is redefined in a later layer.

### `merge=false`

| Requested layer | Result |
|-----------------|--------|
| Main db (`extension_filter` = main name or base only) | Rows with `source_db_name` = main only |
| Extension db | Rows from that extension only; adopted role without `Rights.xml` → **empty** |
| Extension-only role | Only that extension’s rows (main has no role) |

### `merge=true` response

Effective merged state. Optional `provenance` per row (`source_db_name`, `extension_purpose`) — post-MVP; not required for first implementation.

---

## MCP tools (config-mcp, planned)

| Tool | Purpose |
|------|---------|
| `find_role` | By name / synonym; `role_qualified_name`, `uuid`, layer |
| `list_roles` | List roles in project/layer |
| `get_role_rights` | **Central tool.** `merge=true` (default) = effective state (main + extensions by purpose priority); `merge=false` = single layer only, no main inheritance. `extension_filter` selects layer when `merge=false`. Filters: `object_name`, `rights`, `rls`, `depth` (`object` / `all`), `include_restriction_text` |
| `find_roles_for_object` | Reverse: roles granting rights on object; filters for right type and RLS |
| `find_referencing_objects` | `via: role_grant` — JOIN `role_grants` (no `metadata_relations` duplicate) |

### MVP tool bounds

**Agreed:** every list field in role tool responses is capped; when the cap is hit, response includes `is_truncated: true` and `total_count` (full count before limit). Agent should narrow filters or raise `max_results`.

| Parameter | Default | Applies to |
|-----------|---------|------------|
| `max_results` | `200` | `grants`, `access_restrictions`, `find_roles_for_object` roles |
| `depth` | `object` | `get_role_rights` — object-level targets only; `all` adds field-level (`*.Attribute.*`, …) |
| `include_restriction_text` | `false` | When `true`: preview first **200** chars per restriction (`restriction_text_preview`); full text only with `include_restriction_text=full` (post-MVP or explicit opt-in) |

`object_name` filter: no grant cap (return all matching rows for that object); `is_truncated` still set if restrictions exceed `max_results`.

Pattern matches existing tools (`list_objects`, `find_referencing_objects`): `is_truncated` + hint to refine query.

#### Why these defaults (АСБ main reference)

Measured across 651 roles:

| Metric | Object-level targets | Field-level (attributes, TS, StandardAttribute, …) |
|--------|---------------------|---------------------------------------------------|
| `<object>` rows in `Rights.xml` | 17 445 (55%) | 14 139 (45%) |
| `<right>` cells | 58 012 (78%) | 16 394 (22%) |
| Avg rights per row | ~3.3 (Read, View, Edit, …) | ~1.15 (usually View/Edit) |

Bulk **right count** comes from whole metadata objects (several right types each), not from requisites alone. `depth=object` drops ~45% of rows but only ~22% of right cells — insufficient alone for heavy roles.

`ПолныеПрава`: 1 616 object rows (8 246 rights) + 422 field rows (556 rights). Top role in config: ~10k rights, field-heavy. Hence **summary mode** + truncation, not skip indexing.

### Heavy and admin roles

**Agreed.** Some roles are huge; `ПолныеПрава` is also semantically “full admin”.

**Indexer:** parse **all** roles into SQLite (~31k grant rows / ~74k right cells in АСБ main — fine for DB size and build time). Do **not** skip parsing main `ПолныеПрава` — extension deltas (e.g. `ФТ_Бюджетирование` → `ПолныеПрава`: 388 objects) must remain queryable.

**Response policy** (`get_role_rights`):

| Condition | Default response |
|-----------|------------------|
| `role_name = ПолныеПрава` and no `object_name` | **`summary`** mode (see below) |
| Any role with `grant_count > max_results` and no `object_name` | **`summary`** mode |
| `object_name` set | Full matching grants for that object (subject to `max_results` / `is_truncated`) |
| `response_mode=full` | Force grant enumeration up to `max_results` |

**`summary` mode payload** (instead of huge `grants` array):

```json
{
  "response_mode": "summary",
  "role_profile": "admin_full",
  "settings": { … },
  "grant_stats": { "object_level": 1616, "field_level": 422, "total_rights": 8802 },
  "access_restrictions": [ … ],
  "extension_delta_grants": [ … ],
  "grants": [],
  "is_truncated": true,
  "total_count": 8802,
  "hint": "Admin role; use object_name filter or response_mode=full for enumeration."
}
```

- `role_profile: admin_full` — only for **`ПолныеПрава`** in MVP (predefined 1C admin role).
- `extension_delta_grants` — grants from extension layer(s) only when `merge=true` and extension has delta `Rights.xml` (the interesting, non-obvious part). Capped by `max_results` separately.
- Other heavy roles (> `max_results`, not `ПолныеПрава`): same summary shape but `role_profile: null` (size-driven, not semantic admin).

**`find_roles_for_object`:** returns roles with **explicit** indexed grants on the object. Footnote when project contains `ПолныеПрава`:

```json
"admin_roles_note": "Role.ПолныеПрава grants broad access by policy; not enumerated per object."
```

`role_profile: admin_full` — **`ПолныеПрава` only** in MVP (by `Name`). Other heavy roles: summary without admin profile. Expand heuristic post-MVP if needed.

`get_role_rights` response shape (illustrative, `response_mode=full`):

```json
{
  "role": { "name": "…", "qualified_name": "Role.…", "uuid": "…" },
  "settings": { "set_for_attributes_by_default": true },
  "merge": true,
  "layers": ["Main (base)", "ФТ_Бюджетирование"],
  "grants": [ … ],
  "access_restrictions": [
    {
      "object": "Catalog.БанковскиеСчета",
      "right": "Read",
      "field_scope": null,
      "restriction_text": "…"
    },
    {
      "object": "Catalog.БанковскиеСчета",
      "right": "Read",
      "field_scope": "Ref",
      "restriction_text": "…"
    }
  ],
  "restriction_templates": [ … ]
}
```

---

## Extensions (observed in reference export)

Extension `ФТ_Бюджетирование`: `AddOn`, prefix `ФТ_`, 19 roles.

| Pattern | Example |
|---------|---------|
| New extension role + full `Rights.xml` | `ФТ_Бюджетирование`, `ФТ_ПросмотрОтчетаБДДС` |
| Adopted role + **delta** `Rights.xml` | `ПолныеПрава` — only added `ФТ_*` grants; own uuid + `ExtendedConfigurationObject` → main uuid |
| Adopted role, metadata only | `ДобавлениеИзменениеДанныхБухгалтерии` — no `Rights.xml` |
| Adopted role, delta added in test | `ЧтениеДанныхБухгалтерии` — `Catalog.ФТ_НаправленияДоговоров` Read/View |

After test edits (`ФТ_Бюджетирование` role): RLS on `Catalog.БанковскиеСчета` Read — two restrictions (прочие поля + `field=Ref`); plain query conditions; `restrictionTemplate` stub.

Main config scale (АСБ main): ~651 roles; ~31k grant rows / ~74k `<right>` cells (78% of cells on object-level targets); ~4095 restrictions (almost all “прочие поля”; one `field=ВерсияОбъекта` in `ЧтениеИнформацииОВерсияхОбъектов`).

---

## Implementation notes

| Area | File(s) |
|------|---------|
| Parse `Roles/*.xml`, `Rights.xml` | `shared/xml_parser/` |
| Schema + materialize | `admin_tool/db_manager/` |
| MCP | `server/tools/`, `server/tool_schemas.py` |
| Version bump | `shared/indexer_version.py` |

Build log: separate stage “Roles / role_grants” (similar to subsystems).

Tier 3 (deferred): parse `#ПоЗначениям` internals, full RLS query analysis, code graph.

---

## Testing

**Agreed:** CI uses a **minimal fixture** (3–5 roles covering the validation checklist below), checked into `tests/fixtures/roles/` — not the full АСБ export. Full АСБ remains manual / local reference for scale checks.

## Open questions

_None — phase 4 spec decisions recorded above. Reopen if implementation surfaces new edge cases._

---

## Validation checklist (reference export)

| Case | Where to verify |
|------|-----------------|
| Прочие поля + `#ПоЗначениям` | Main: `ЧтениеЭЛН` → `InformationRegister.СведенияОбЭЛН` Read |
| Field-specific restriction | Main: `ЧтениеИнформацииОВерсияхОбъектов` → `InformationRegister.ВерсииОбъектов`, field `ВерсияОбъекта` |
| Two restrictions on one right | Ext: `ФТ_Бюджетирование` → `Catalog.БанковскиеСчета` Read |
| Adopted + delta Rights | Ext: `ЧтениеДанныхБухгалтерии`, `ПолныеПрава` |
| Adopted, no Rights | Ext: `ДобавлениеИзменениеДанныхБухгалтерии` |
| Role flags | Main: `ПолныеПрава` `setForNewObjects=true`; ext delta `setForAttributesByDefault=false` |
