# Unified 1C AI Admin Hub — Protocol v1.0.3 Addendum

## Document status

Addendum to [`protocol-v1.md`](protocol-v1.md), [`protocol-v1.0.1-addendum.md`](protocol-v1.0.1-addendum.md) and [`protocol-v1.0.2-addendum.md`](protocol-v1.0.2-addendum.md).

**Goal:** remove ambiguity in JSON encoding for headless CLI of managed tools. Without this, Hub clients (ConfigAdmin, CI, automation) get incorrect Unicode strings when reading subprocess stdout on Windows.

On conflict with earlier versions, v1.0.3 takes priority as the later normative version.

---

## 1. Problem (observed behavior)

During ConfigAdmin ↔ config-mcp integration (Phase 2) a mismatch was found:

| Channel | Expected | Actual (Windows, before fix) |
|---------|----------|------------------------------|
| `projects.json` on disk | UTF-8 | UTF-8 |
| `apply-registry --input <file>` | UTF-8 without BOM | UTF-8 without BOM |
| `status --json` / `inventory --json` stdout | UTF-8 | CP1251 (Windows console encoding) |

**Symptom:** Cyrillic `name` in JSON becomes U+FFFD when decoding stdout as UTF-8.

**Cause:** Python CLI on Windows writes to stdout via text stream with system encoding (often CP1251), not UTF-8. For frozen/PyInstaller builds `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` **do not guarantee** UTF-8 on stdout.

**Conclusion:** managed tool must emit normative UTF-8 JSON; Hub client must not "guess" locale.

---

## 2. Normative requirement: UTF-8 for all JSON I/O

### 2.1. Scope

Requirement applies to **all managed tools** (`config-mcp`, `help-mcp`, `data-mcp`, `config-admin`):

- any call with `--json` flag;
- any `--input` / `--output` file containing JSON payload (incl. `apply-registry`, `export-registry`).

### 2.2. stdout (`--json`)

With `--json`:

- **stdout** contains **only one JSON document** (as in v1 §8.1);
- stdout encoding: **UTF-8**;
- **no BOM** (byte order mark forbidden);
- JSON: Unicode characters passed literally (not `\uXXXX` escape), `ensure_ascii=false` for Python;
- trailing newline allowed (`\n`), not required.

### 2.3. stderr

- **stderr** — human-readable diagnostics;
- UTF-8 recommended;
- stderr **is not** a JSON channel.

### 2.4. File I/O

| Operation | Encoding | BOM |
|-----------|----------|-----|
| `--input <file.json>` | UTF-8 | forbidden |
| atomic write registry/config files | UTF-8 | forbidden |
| read existing config files | UTF-8 (primary); CP1251 fallback **only on read** for legacy files, write back as UTF-8 | — |

**Symmetry:** if `apply-registry --input` requires UTF-8 without BOM, then `status --json` stdout must be UTF-8 without BOM.

### 2.5. Relation to RFC 8259

Machine-readable JSON in Admin Hub — **UTF-8 JSON** per RFC 8259. Locale-dependent encoding (CP1251, CP866) on stdout is **incompatible** with protocol v1.0.3+.

---

## 3. Changes to Protocol v1 §8.1 (wording for merge)

**Was (v1 §8.1):**

> stdout: only machine-readable JSON.

**Now (v1.0.3 §8.1):**

> stdout: only machine-readable JSON in **UTF-8 without BOM**.  
> stderr: diagnostics/log hints; UTF-8 recommended.  
> JSON input files (`--input`): UTF-8 without BOM.

---

## 4. Implementation requirements (config-mcp / Python CLI)

### 4.1. Required (MUST)

Before emitting JSON to stdout, CLI **must not** rely on `sys.stdout.encoding` / Windows console code page.

**Recommended pattern:**

```python
import json
import sys

def write_json_stdout(payload: object) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(data.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
```

**Alternative (Python 3.7+):**

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
print(json.dumps(payload, ensure_ascii=False, indent=2))
```

Prefer `sys.stdout.buffer` — independent of text wrapper and PyInstaller.

### 4.2. Reading `--input`

```python
def read_json_file(path: Path) -> object:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed in JSON input")
    return json.loads(raw.decode("utf-8"))
```

### 4.3. Forbidden (MUST NOT)

- rely on `PYTHONIOENCODING` / `PYTHONUTF8` as the only mechanism for portable builds;
- write JSON via `print()` without forced UTF-8 on Windows;
- emit JSON in CP1251/CP866 even "for console convenience".

### 4.4. Portable / PyInstaller

In `module.manifest.json` (optional discovery):

```json
"cliContract": {
  "jsonEncoding": "utf-8",
  "jsonBom": false
}
```

---

## 5. Verification (acceptance criteria)

### 5.1. CLI autotest

```bash
<cli> --root "<portable>" status --json > out.bin
```

Checks:

1. First 3 bytes are **not** `EF BB BF` (no BOM).
2. `out.bin` decodes as UTF-8 **without** U+FFFD.
3. `"name"` field with Cyrillic matches `projects.json` on disk.

### 5.2. Cross-platform

Same portable + test passes on Windows 10/11 (ru-RU locale) and Linux (UTF-8 locale).

### 5.3. Regression

- `apply-registry --input fragment.json --json` continues to work with UTF-8 without BOM;
- BOM in input rejected with clear error.

---

## 6. Impact on Hub clients

ConfigAdmin Phase 2 used temporary workaround: UTF-8 first, fallback CP1251 on U+FFFD on Windows. After config-mcp fix workaround can be removed or kept behind feature flag `legacyCliEncoding` for 1–2 releases.

---

## 7. Scope and priority

| Module | Priority | Commands |
|--------|----------|----------|
| **config-mcp** | **P0** | `inventory`, `status`, `export-registry`, `apply-registry` |
| help-mcp | P1 | all `--json` |
| data-mcp | P1 | all `--json` |
| config-admin | P1 | protocol CLI |

---

## 8. config-mcp implementation status

**Implemented** in `shared/cli_json.py` + `admin_tool/cli.py`:

- `write_json_stdout()` via `sys.stdout.buffer` + UTF-8;
- `read_json_file()` with BOM reject;
- tests `tests/test_cli_json_encoding.py`.

After portable rebuild (`build_all.bat`) deviation "stdout CP1251 on Windows" is **closed**.

---

*Protocol v1.0.3 — prepared by ConfigAdmin team, 2026-06-28. Context: Phase 2 integration, portable `1c_config_mcp_server_Portable`.*
