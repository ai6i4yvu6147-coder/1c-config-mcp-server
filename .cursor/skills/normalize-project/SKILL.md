---
name: normalize-project
description: >-
  Normalize this repository (S/H/Sub) per WI canon and role checklist.
disable-model-invocation: true
---

# Normalize project

Роль: **S** | **H** | **Sub** (уточни, если не указана).

Путь к WI: `WORKSPACE_IMPROVE`.

## Процедура

1. Каноны по роли:
   - **S:** `normalize-governance.md`, `project-structure.md`, `normalize-merge.md`, `documentation.md`
   - **H / Sub:** то же + `group-sync.md`
2. Чеклист: `<WI>/normalize.bundle.yaml` для выбранной роли.
3. Привести репозиторий к чеклисту; шаблоны из `<WI>/templates/`. Agents — полные копии из `templates/agents/*.md`.
4. Docs к канону: skill **`maintain-docs`** → **`doc-librarian`** (не массовые правки в родительском чате).
5. `docs/normalize-record.md`, `project-doctor`, отчёт.
