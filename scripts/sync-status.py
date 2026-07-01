#!/usr/bin/env python3
"""
Group sync status: inbox counts, protocol_sync_state hints from integration/README.

Usage:
  python sync-status.py --repo <path>
  python sync-status.py --operator-check --repo <path> [--stale-hours N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

GROUP = Path("docs/group")
DEFAULT_STALE_HOURS = 4


def _loose_packets(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.md") if p.is_file())


def _snapshot_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_dir()
        and (p.name.startswith("protocol-snapshot-") or p.name.startswith("review-snapshot-"))
    )


def _age_hours(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 3600.0


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


def _report_pending(label: str, directory: Path, stale_hours: float) -> list[str]:
    hints: list[str] = []
    packets = _loose_packets(directory)
    snaps = _snapshot_dirs(directory)
    if not packets and not snaps:
        return hints

    print(f"  {label}:")
    for p in packets:
        age = _age_hours(p)
        flag = " [STALE]" if age > stale_hours else ""
        print(f"    - {p.name} ({age:.1f}h){flag}")
    for p in snaps:
        age = _age_hours(p)
        flag = " [STALE]" if age > stale_hours else ""
        print(f"    - {p.name}/ ({age:.1f}h){flag}")

    if packets or snaps:
        hints.append(label)
    return hints


def status(repo: Path) -> int:
    role = _manifest_role(repo)
    print(f"sync-status: {repo}")
    print(f"  role: {role}")

    if role == "head":
        outbox_root = repo / GROUP / "outbox"
        if outbox_root.is_dir():
            for sub_dir in sorted(outbox_root.iterdir()):
                if not sub_dir.is_dir():
                    continue
                sid = sub_dir.name
                out_md = len(_loose_packets(sub_dir))
                snaps = len(_snapshot_dirs(sub_dir))
                in_md = len(_loose_packets(repo / GROUP / "inbox" / sid))
                print(f"  sub {sid}: outbox {out_md} md, {snaps} dir(s); inbox {in_md} md")
    elif role == "subordinate":
        out_md = len(_loose_packets(repo / GROUP / "outbox"))
        in_md = len(_loose_packets(repo / GROUP / "inbox"))
        snaps = len(_snapshot_dirs(repo / GROUP / "inbox"))
        print(f"  outbox: {out_md} md; inbox: {in_md} md, {snaps} dir(s)")
        fields = _parse_integration_fields(repo / GROUP / "integration.md")
        if fields:
            print("  integration.md:")
            for k, v in fields.items():
                print(f"    {k}: {v or '-'}")
    else:
        for name in ("inbox", "outbox"):
            d = repo / GROUP / name
            print(f"  {name}: {len(_loose_packets(d))} md")

    return 0


def operator_check(repo: Path, stale_hours: float) -> int:
    role = _manifest_role(repo)
    print(f"sync-status operator-check: {repo}")
    print(f"  role: {role}")
    print(f"  stale threshold: {stale_hours}h")
    print()

    pending_out: list[str] = []
    pending_in: list[str] = []

    if role == "head":
        outbox_root = repo / GROUP / "outbox"
        if outbox_root.is_dir():
            for sub_dir in sorted(outbox_root.iterdir()):
                if sub_dir.is_dir():
                    pending_out.extend(_report_pending(f"outbox/{sub_dir.name}", sub_dir, stale_hours))
        inbox_root = repo / GROUP / "inbox"
        if inbox_root.is_dir():
            for sub_dir in sorted(inbox_root.iterdir()):
                if sub_dir.is_dir():
                    pending_in.extend(_report_pending(f"inbox/{sub_dir.name}", sub_dir, stale_hours))

        if pending_out:
            print()
            print("  → Оператор: скопировать outbox → Sub inbox (см. OPERATOR-HANDOFF.md)")
            print("  → Затем Sub: skill sync / «обработай inbox»")
        if pending_in:
            print()
            print("  → Head: skill sync / «обработай inbox»")

    elif role == "subordinate":
        pending_out.extend(_report_pending("outbox", repo / GROUP / "outbox", stale_hours))
        pending_in.extend(_report_pending("inbox", repo / GROUP / "inbox", stale_hours))

        if pending_out:
            print()
            print("  → Оператор: скопировать outbox → Head inbox/<sub-id>/")
            print("  → Затем Head: skill sync / «обработай inbox»")
        if pending_in:
            print()
            print("  → Sub: skill sync / «обработай inbox»")

    else:
        pending_out.extend(_report_pending("outbox", repo / GROUP / "outbox", stale_hours))
        pending_in.extend(_report_pending("inbox", repo / GROUP / "inbox", stale_hours))

    if not pending_out and not pending_in:
        print("  (empty — нет ожидающих пакетов)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Group sync status summary")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--operator-check", action="store_true")
    parser.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        return 2
    if args.operator_check:
        return operator_check(repo, args.stale_hours)
    return status(repo)


if __name__ == "__main__":
    sys.exit(main())
