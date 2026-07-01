# Каноны структуры проектов

Версия: **2.1.0**

Универсальный стандарт для **любых** репозиториев. Не привязан к конкретному стеку или домену.

---

## Три типа проекта

| Код | Тип | Когда использовать |
|-----|-----|-------------------|
| **S** | Standalone (обычный) | Автономный проект без группы |
| **H** | Head (головной) | Владеет общей документацией группы, координирует подчинённые |
| **Sub** | Subordinate (подчинённый) | Входит в группу; локальные спеки + синхронизация через пакеты |

Любой проект **сначала** соответствует базе **S**. Тип H и Sub — расширения поверх базы.

---

## База (все типы: S, H, Sub)

```
<project>/
├── README.md
├── AGENTS.md
├── CHANGELOG.md
├── .gitignore
├── src/
├── tests/
├── fixtures/               # опционально
├── scripts/                # опционально
└── docs/
    ├── README.md
    ├── agent-onboarding.md
    ├── architecture.md
    ├── todo.md
    └── …
```

### Что не коммитить (все типы)

- `venv/`, `node_modules/`, `build/`, `dist/`
- Runtime-конфиги — только `*.example.json` / `.env.example`
- `plans/`, `scratch/`
- **Транспорт группы:** `docs/group/inbox/`, `docs/group/outbox/` — ephemeral, в `.gitignore`

---

## Расширение H (головной проект)

```
<head>/
├── …база S…
├── group.manifest.yaml
└── docs/
    └── group/
        ├── README.md
        ├── shared/              # КАНОН общей документации (редактируется только здесь)
        ├── outbox/
        │   └── <sub-id>/        # исходящие пакеты (gitignored)
        └── inbox/
            └── <sub-id>/        # входящие от Sub (gitignored)
```

**Обязательно:** `group.manifest.yaml` (`role: head`), `docs/group/README.md`, `docs/group/shared/`

---

## Расширение Sub (подчинённый проект)

```
<subordinate>/
├── …база S…
├── group.manifest.yaml          # рекомендуется: role subordinate + путь к Head
└── docs/
    └── group/
        ├── integration.md       # связь с Head, локальные отклонения, last_sync_*
        ├── inbox/               # пакеты от Head (gitignored)
        └── outbox/              # пакеты для Head (gitignored)
```

**Обязательно:** `docs/group/integration.md`

**Не делать в Sub:**

- Держать канон общего протокола — только в Head `docs/group/shared/`
- Коммитить sync-пакеты в git
- Общаться с другими Sub напрямую — только через Head

---

## Матрица обязательных элементов

| Элемент | S | H | Sub |
|---------|:-:|:-:|:-:|
| `README.md`, `AGENTS.md`, `CHANGELOG.md` | ✅ | ✅ | ✅ |
| `docs/{README,agent-onboarding,architecture,todo}.md` | ✅ | ✅ | ✅ |
| `group.manifest.yaml` | — | ✅ | рекомендуется |
| `docs/group/README.md` | — | ✅ | — |
| `docs/group/shared/` | — | ✅ | — |
| `docs/group/integration.md` | — | — | ✅ |
| `docs/group/inbox/`, `outbox/` в `.gitignore` | — | ✅ | ✅ |

---

## Запрещено (все типы)

| Антипаттерн | Правильно |
|-------------|-----------|
| `readme.txt` вместо `README.md` | `README.md` |
| Длинные спеки в корне | `docs/` |
| Sync-пакеты в git | `.gitignore` + удаление после обработки |
| Sub ↔ Sub напрямую | только через Head |
| Зеркальная копия `shared/` в Sub | пакеты + локальная адаптация спек |

Шаблоны: `../../templates/standalone/`, `head/`, `subordinate/`
