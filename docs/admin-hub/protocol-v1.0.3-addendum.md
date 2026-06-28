# Unified 1C AI Admin Hub — Protocol v1.0.3 Addendum

## Статус документа

Дополнение к [`protocol-v1.md`](protocol-v1.md), [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) и [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md).

**Цель:** устранить неоднозначность кодировки JSON в headless CLI managed tools. Без этого Hub-клиенты (ConfigAdmin, CI, automation) получают некорректные Unicode-строки при чтении stdout subprocess на Windows.

При конфликте с более ранними версиями приоритет имеет v1.0.3 как более поздняя нормативная версия.

---

## 1. Проблема (observed behavior)

При интеграции ConfigAdmin ↔ config-mcp (Phase 2) выявлено расхождение:

| Канал | Ожидаемое | Фактически (Windows, до fix) |
|-------|-----------|------------------------------|
| `projects.json` на диске | UTF-8 | UTF-8 |
| `apply-registry --input <file>` | UTF-8 без BOM | UTF-8 без BOM |
| `status --json` / `inventory --json` stdout | UTF-8 | CP1251 (консольная кодировка Windows) |

**Симптом:** кириллические `name` в JSON превращаются в U+FFFD при декодировании stdout как UTF-8.

**Причина:** Python CLI на Windows пишет в stdout через text stream с системной кодировкой (часто CP1251), а не UTF-8. Для frozen/PyInstaller-сборок переменные `PYTHONIOENCODING=utf-8` и `PYTHONUTF8=1` **не гарантируют** UTF-8 на stdout.

**Вывод:** managed tool обязан выдавать нормативный UTF-8 JSON; Hub-клиент не должен «угадывать» локаль.

---

## 2. Нормативное требование: UTF-8 для всех JSON I/O

### 2.1. Область действия

Требование распространяется на **все managed tools** (`config-mcp`, `help-mcp`, `data-mcp`, `config-admin`):

- любой вызов с флагом `--json`;
- любой `--input` / `--output` файл, содержащий JSON payload (в т.ч. `apply-registry`, `export-registry`).

### 2.2. stdout (`--json`)

При `--json`:

- **stdout** содержит **только один JSON-документ** (как в v1 §8.1);
- кодировка stdout: **UTF-8**;
- **без BOM** (byte order mark запрещён);
- JSON: Unicode-символы передаются literally (не `\uXXXX` escape), `ensure_ascii=false` для Python;
- перевод строки в конце документа допустим (`\n`), но не обязателен.

### 2.3. stderr

- **stderr** — human-readable diagnostics;
- рекомендуется UTF-8;
- stderr **не является** каналом JSON.

### 2.4. Файловый ввод/вывод

| Операция | Кодировка | BOM |
|----------|-----------|-----|
| `--input <file.json>` | UTF-8 | запрещён |
| atomic write registry/config files | UTF-8 | запрещён |
| чтение существующих config-файлов | UTF-8 (primary); допустим fallback CP1251 **только при read** legacy-файлов, с записью обратно в UTF-8 | — |

**Симметрия:** если `apply-registry --input` требует UTF-8 без BOM, то и `status --json` stdout обязан быть UTF-8 без BOM.

### 2.5. Связь с RFC 8259

Machine-readable JSON в Admin Hub — **UTF-8 JSON** по RFC 8259. Locale-dependent кодировка (CP1251, CP866) на stdout **несовместима** с протоколом v1.0.3+.

---

## 3. Изменения в Protocol v1 §8.1 (формулировка для merge)

**Было (v1 §8.1):**

> stdout: только machine-readable JSON.

**Стало (v1.0.3 §8.1):**

> stdout: только machine-readable JSON в кодировке **UTF-8 без BOM**.  
> stderr: diagnostics/log hints; рекомендуется UTF-8.  
> JSON input files (`--input`): UTF-8 без BOM.

---

## 4. Требования к реализации (config-mcp / Python CLI)

### 4.1. Обязательно (MUST)

Перед выводом JSON в stdout CLI **не должен** полагаться на `sys.stdout.encoding` / кодовую страницу консоли Windows.

**Рекомендуемый паттерн:**

```python
import json
import sys

def write_json_stdout(payload: object) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(data.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
```

**Альтернатива (Python 3.7+):**

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
print(json.dumps(payload, ensure_ascii=False, indent=2))
```

Предпочтителен вариант через `sys.stdout.buffer` — он не зависит от text wrapper и PyInstaller.

### 4.2. Чтение `--input`

```python
def read_json_file(path: Path) -> object:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed in JSON input")
    return json.loads(raw.decode("utf-8"))
```

### 4.3. Запрещено (MUST NOT)

- полагаться на `PYTHONIOENCODING` / `PYTHONUTF8` как единственный механизм для portable-сборки;
- писать JSON через `print()` без принудительного UTF-8 на Windows;
- emit JSON в CP1251/CP866 даже «для удобства консоли».

### 4.4. Portable / PyInstaller

В `module.manifest.json` (optional discovery):

```json
"cliContract": {
  "jsonEncoding": "utf-8",
  "jsonBom": false
}
```

---

## 5. Верификация (acceptance criteria)

### 5.1. Автотест CLI

```bash
<cli> --root "<portable>" status --json > out.bin
```

Проверки:

1. Первые 3 байта **не** `EF BB BF` (no BOM).
2. `out.bin` декодируется как UTF-8 **без** U+FFFD.
3. Поле `"name"` с кириллицей совпадает с `projects.json` на диске.

### 5.2. Cross-platform

Один и тот же portable + тест проходит на Windows 10/11 (ru-RU locale) и Linux (UTF-8 locale).

### 5.3. Regression

- `apply-registry --input fragment.json --json` продолжает работать с UTF-8 без BOM;
- BOM во input отклоняется с понятной ошибкой.

---

## 6. Влияние на Hub-клиентов

ConfigAdmin Phase 2 использовал временный workaround: UTF-8 first, fallback CP1251 при U+FFFD на Windows. После исправления config-mcp workaround можно удалить или оставить за feature flag `legacyCliEncoding` на 1–2 релиза.

---

## 7. Scope и приоритет

| Модуль | Приоритет | Команды |
|--------|-----------|---------|
| **config-mcp** | **P0** | `inventory`, `status`, `export-registry`, `apply-registry` |
| help-mcp | P1 | все `--json` |
| data-mcp | P1 | все `--json` |
| config-admin | P1 | protocol CLI |

---

## 8. config-mcp implementation status

**Реализовано** в `shared/cli_json.py` + `admin_tool/cli.py`:

- `write_json_stdout()` через `sys.stdout.buffer` + UTF-8;
- `read_json_file()` с reject BOM;
- тесты `tests/test_cli_json_encoding.py`.

После пересборки portable (`build_all.bat`) deviation «stdout CP1251 on Windows» **снимается**.

---

*Protocol v1.0.3 — подготовлено ConfigAdmin team, 2026-06-28. Контекст: интеграция Phase 2, portable `1c_config_mcp_server_Portable`.*
