#!/usr/bin/env python3
"""
Group sync status (hub model, canon 2.6.0).

Reports the lightweight ## Hub pending signal from docs/todo.md, plus the
GROUP-HUB.md registry (Head) or integration.md protocol fields (Sub).

Usage:
  python sync-status.py --repo <path>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

GROUP = Path("docs/group")


def _manifest_role(repo: Path) -> str:
    if yaml is None:
        return "?"
    p = repo / "group.manifest.yaml"
    if not p.is_file():
        return "standalone"
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("role", "?")


def _hub_pending(repo: Path) -> list[str]:
    todo = repo / "docs/todo.md"
    if not todo.is_file():
        return []
    items: list[str] = []
    in_section = False
    for line in todo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## Hub pending"):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            break
        if in_section and line.lstrip().startswith("- [ ]"):
            items.append(line.strip())
    return items


def _registry_rows(hub: Path) -> list[str]:
    if not hub.is_file():
        return []
    rows: list[str] = []
    in_reg = False
    for line in hub.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## Registry"):
            in_reg = True
            continue
        if line.startswith("## ") and in_reg:
            break
        if in_reg and line.strip().startswith("|") and "sub_id" not in line and "---" not in line:
            rows.append(line.strip())
    return rows


def _active_threads(hub: Path) -> int:
    if not hub.is_file():
        return 0
    return len(re.findall(r"^### THR-", hub.read_text(encoding="utf-8", errors="replace"), re.M))


def _integration_fields(repo: Path) -> dict[str, str]:
    path = repo / GROUP / "integration.md"
    if not path.is_file():
        return {}
    keys = ("sync_state", "last_event")
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2 and cells[0] in keys:
            fields[cells[0]] = cells[1]
    return fields


def status(repo: Path) -> int:
    role = _manifest_role(repo)
    print(f"sync-status: {repo}")
    print(f"  role: {role}")

    pending = _hub_pending(repo)
    print(f"  Hub pending: {len(pending)}")
    for item in pending:
        print(f"    {item}")

    if role == "head":
        hub = repo / "GROUP-HUB.md"
        rows = _registry_rows(hub)
        print(f"  GROUP-HUB.md: {'present' if hub.is_file() else 'MISSING'}, "
              f"{len(rows)} sub(s), {_active_threads(hub)} active thread(s)")
        for row in rows:
            print(f"    {row}")
    elif role == "subordinate":
        fields = _integration_fields(repo)
        if fields:
            print("  integration.md:")
            for k, v in fields.items():
                print(f"    {k}: {v or '-'}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Group sync status (hub model)")
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        return 2
    return status(repo)


if __name__ == "__main__":
    sys.exit(main())
