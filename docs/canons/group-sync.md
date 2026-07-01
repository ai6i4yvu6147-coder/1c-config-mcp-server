# Канон: синхронизация документации группы

Версия: **2.2.0**

Пакетная синхронизация **Head ↔ Sub** (star-топология). Baseline протокола + дельты после `stable`.

---

## Принципы

1. **Head** — хранитель канона (`docs/group/shared/`).
2. **Sub** — локальные спеки + `integration.md` + `protocol-ref/epoch<N>/`.
3. **Sub ↔ Sub** — запрещено; только через Head.
4. **Relay** переносит пакеты и snapshot-каталоги; **doc-librarian** правит docs; **group-sync-arbitrator** (H/Sub) — вердикты.
5. Inbox/outbox **не в git**; `protocol-ref/` и `shared/` — коммитить.

---

## Состояния протокола

| state | Значение |
|-------|----------|
| `negotiating` | offer / dispute / merge в процессе |
| `stable` | Sub принял текущий `protocol_epoch` |
| `stale` | Head поднял epoch; Sub ещё не принял ripple |

Поля: `protocol_epoch`, `protocol_sync_state`, `stable_at`, `open_disputes`, `dispute_round` (max 3 → `defer_manual`).

Head ведёт таблицу Sub в `docs/group/README.md`: `sub_id | epoch | state | last_ack`.

---

## Режимы синхронизации

| Режим | Когда |
|-------|-------|
| **Baseline / reconcile** | Первое выравнивание, дрейф протокола |
| **`sync_delta`** | После `stable` у группы |

### Каскад

offer → (librarian) → dispute/ack → (arbitrator на H) → merge → ripple → calm на всех Sub.

Критичное изменение Sub A доходит до Sub B **только через Head**.

---

## Типы пакетов (`kind`)

| kind | direction | Содержание |
|------|-----------|------------|
| `protocol_offer` | H→Sub | Snapshot-каталог + summary |
| `protocol_dispute` | Sub→H | Расхождения, предложение Sub |
| `protocol_merge` | H→Sub | Вердикт + изменения shared |
| `protocol_ack` | любой | epoch принят → stable |
| `protocol_ripple` | H→Sub | Канон изменён; новый offer |
| `sync_delta` | любой | Дельта после stable |

Шаблон dispute: `../../templates/protocol-dispute.example.md`  
Шаблон delta: `../../templates/sync-packet.example.md`

---

## Топология и каталоги

### Head

```
docs/group/outbox/<sub-id>/<packet>.md
docs/group/outbox/<sub-id>/protocol-snapshot-epoch<N>-<ts>/
docs/group/inbox/<sub-id>/<packet>.md
```

### Sub

```
docs/group/inbox/<packet>.md
docs/group/inbox/protocol-snapshot-epoch<N>-<ts>/
docs/group/outbox/<packet>.md
docs/group/protocol-ref/epoch<N>/    # stable copy, в git
```

---

## Формат пакета (общее)

```yaml
---
packet_version: 1
kind: sync_delta
from: <module-id>
to: <module-id>
direction: head_to_sub | sub_to_head
severity: critical | info
protocol_epoch: <N>
affects:
  - docs/group/integration.md
summary: |
  ...
---
```

После обработки: удалить пакет из inbox.

---

## group.manifest.yaml

### Head

```yaml
group:
  id: <group-id>
  canon_version: "2.2.0"
role: head
subordinates:
  - id: <sub-id>
    path: C:/projects/<sub-repo>
```

### Sub

```yaml
id: <sub-module-id>
group:
  id: <group-id>
role: subordinate
head:
  id: <head-id>
  path: C:/projects/<head-repo>
```

---

## Инструменты

```powershell
python scripts/sync-relay.py --deliver --repo .
python scripts/sync-relay.py --status --repo .
python scripts/protocol-snapshot.py --export --repo . --sub <id>
python scripts/protocol-snapshot.py --install --repo .
python scripts/sync-status.py --repo .
```

---

## Субагенты и skills

| Агент | Роли |
|-------|------|
| `doc-librarian` | S, H, Sub |
| `group-sync-arbitrator` | H, Sub |

| Skill | Когда |
|-------|-------|
| `export-group-protocol` | Head: offer |
| `import-group-protocol` | Sub: принять offer |
| `review-protocol-diff` | Sub: gate перед dispute |
| `arbitrate-protocol-dispute` | Head: вердикт |
| `run-protocol-reconciliation` | Полный цикл |
| `emit-group-sync-packet` | Дельта после stable |
| `process-group-inbox` | Входная точка inbox (маршрутизация по `kind`) |
| `canon-align` | Структура репо через `project-doctor.py` |

Шаблоны: `../../templates/skills/`, `../../templates/agents/`

---

## Пример группы

`../../examples/1c-cursor-group.manifest.yaml`
