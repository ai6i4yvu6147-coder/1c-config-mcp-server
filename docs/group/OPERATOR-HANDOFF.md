# Operator handoff — групповая синхронизация

Агенты пишут пакеты в **outbox**; оператор копирует в **inbox** соседнего репозитория и сообщает агенту: «inbox готов» / «обработай inbox».

---

## Пути

| Роль | Репозиторий |
|------|-------------|
| Head | `C:/projects/1c-admin-tool` |
| Sub `1c-config-mcp` | `C:/projects/1c-config-mcp` |

---

## Копирование

### Head → Sub

| Откуда | Куда |
|--------|------|
| `Head/docs/group/outbox/1c-config-mcp/*.md` | `Sub/docs/group/inbox/` |
| `Head/docs/group/outbox/1c-config-mcp/protocol-snapshot-*` | `Sub/docs/group/inbox/` |
| `Head/docs/group/outbox/1c-config-mcp/review-snapshot-*` | `Sub/docs/group/inbox/` |

### Sub → Head

| Откуда | Куда |
|--------|------|
| `Sub/docs/group/outbox/*.md` | `Head/docs/group/inbox/1c-config-mcp/` |
| `Sub/docs/group/outbox/protocol-snapshot-*` | `Head/docs/group/inbox/1c-config-mcp/` |

---

## Чеклист цикла согласования

1. Head: `/sync-base 1c-config-mcp` или `/sync 1c-config-mcp <topic>` → файлы в outbox Head.
2. Оператор: копия в Sub inbox.
3. Sub: «обработай inbox» (skill `sync`) → dispute или ack в outbox Sub.
4. Оператор: копия в Head inbox.
5. Head: «обработай inbox» → merge или закрытие ack.
6. Повторять 2–5 до `protocol_ack` и stable.
7. После ack: удалить обработанные файлы из inbox; убрать устаревшие пакеты из outbox отправителя.
8. Inbox/outbox **не коммитить** в git.

---

## Подсказка

```powershell
python scripts/sync-status.py --operator-check --repo .
```
