#!/usr/bin/env python3
"""
Group sync status: inbox counts, protocol_sync_state hints from integration/README.

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


def _count_packets(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.rglob("*") if p.is_file() and p.suffix == ".md")


def _count_snapshots(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        p.name for p in directory.iterdir() if p.is_dir() and p.name.startswith("protocol-snapshot-")
    )


def _parse_integration_fields(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" not in line or line.strip().startswith("#"):
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2 and cells[0] in (
            "protocol_epoch",
            "protocol_sync_state",
            "stable_at",
            "dispute_round",
            "open_disputes",
        ):
            fields[cells[0]] = cells[1]
    return fields


def _manifest_role(repo: Path) -> str:
    if yaml is None:
        return "?"
    p = repo / "group.manifest.yaml"
    if not p.is_file():
        return "standalone"
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("role", "?")


def status(repo: Path) -> int:
    role = _manifest_role(repo)
    print(f"sync-status: {repo}")
    print(f"  role: {role}")

    if role == "head":
        for sub_dir in sorted((repo / GROUP / "outbox").iterdir()) if (repo / GROUP / "outbox").is_dir() else []:
            if not sub_dir.is_dir():
                continue
            sid = sub_dir.name
            out_md = _count_packets(sub_dir)
            snaps = _count_snapshots(sub_dir)
            in_dir = repo / GROUP / "inbox" / sid
            in_md = _count_packets(in_dir)
            print(f"  sub {sid}: outbox {out_md} md, {len(snaps)} snapshot(s); inbox {in_md} md")
    elif role == "subordinate":
        out_md = _count_packets(repo / GROUP / "outbox")
        in_md = _count_packets(repo / GROUP / "inbox")
        snaps = _count_snapshots(repo / GROUP / "inbox")
        print(f"  outbox: {out_md} md; inbox: {in_md} md, {len(snaps)} snapshot(s)")
        fields = _parse_integration_fields(repo / GROUP / "integration.md")
        if fields:
            print("  integration.md:")
            for k, v in fields.items():
                print(f"    {k}: {v or '-'}")
    else:
        for name in ("inbox", "outbox"):
            d = repo / GROUP / name
            print(f"  {name}: {_count_packets(d)} md")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Group sync status summary")
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        return 2
    return status(repo)


if __name__ == "__main__":
    sys.exit(main())
