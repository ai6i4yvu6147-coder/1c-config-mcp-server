# Roles and access restrictions (phase 4 — intermediate spec)

**Status:** intermediate spec · design agreed in discussion · **not implemented**

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

Pairs inside `#ПоЗначениям("…", "Организации", "Организация", …)` are **parameters of one restriction** for “прочие поля”, not separate UI rows. Optional MVP+ parse as `access_kind_hints` for data-mcp; do not split into separate restriction rows.

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

### `metadata_relations` (denormalized, optional)

`relation_kind = **role_grant**` (canonical; replace test placeholder `role_right`): role → target object for coarse reverse lookup in `find_referencing_objects`. Detail (right, RLS) stays in grant/restriction tables.

---

## MCP tools (config-mcp, planned)

| Tool | Purpose |
|------|---------|
| `find_role` | By name / synonym; `role_qualified_name`, `uuid`, layer |
| `list_roles` | List roles in project/layer |
| `get_role_rights` | **Central tool.** `merge=true` (default) = effective state; `merge=false` + `extension_filter` = single layer. Filters: `object_name`, `rights`, `rls`, `depth` (`object` / `all`), `include_restriction_text` |
| `find_roles_for_object` | Reverse: roles granting rights on object; filters for right type and RLS |
| `find_referencing_objects` | Extended with `via: role_grant` (coarse) |

`get_role_rights` response shape (illustrative):

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

Main config scale (АСБ main): ~651 roles, ~57k object-level grants, ~17k field-level grants, ~4095 restrictions (almost all “прочие поля”; one `field=ВерсияОбъекта` in `ЧтениеИнформацииОВерсияхОбъектов`).

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

## Open questions

1. **Merge semantics** — formal rules when combining main + extension(s): overlay grants? restrictions? conflict resolution (`true` vs `false`)? adopted role without extension `Rights.xml` = inherit main only?
2. **MVP tool bounds** — default `get_role_rights` depth (`object` only?), max rows, full vs preview `restriction_text`
3. **`#ПоЗначениям` parsing** — store raw text only in MVP, or extract `access_kind` / field pairs as hints for data-mcp?
4. **`metadata_relations.role_grant`** — materialize for every object-level grant, or only for `find_referencing_objects` coarse index?
5. **data-mcp spec** — contract only in this doc, or separate doc / protocol addendum for template tools?
6. **CI fixture** — minimal role subset export (3–5 roles) vs full АСБ for tests?
7. **Adopted role identity** — merge by `name`, by `ExtendedConfigurationObject`, or both in API?

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
