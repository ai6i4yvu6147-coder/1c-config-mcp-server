#!/usr/bin/env python3
"""
Доставка sync-пакетов между Head и Sub по group.manifest.yaml.

Переносит файлы outbox отправителя -> inbox получателя. Не правит спеки.

Usage:
  python sync-relay.py --deliver --repo <sender-path>
  python sync-relay.py --deliver --dry-run --repo <sender-path>
  python sync-relay.py --status --repo <any-path>
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

GROUP_DOCS = Path("docs/group")


def load_manifest(repo: Path) -> dict | None:
    manifest_path = repo / "group.manifest.yaml"
    if not manifest_path.is_file():
        return None
    if yaml is None:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    with manifest_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _norm(p: Path) -> Path:
    return p.resolve()


def iter_packets(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file())


def head_outbox_packets(head: Path, sub_id: str) -> list[Path]:
    return iter_packets(head / GROUP_DOCS / "outbox" / sub_id)


def head_inbox_dir(head: Path, sub_id: str) -> Path:
    return head / GROUP_DOCS / "inbox" / sub_id


def sub_outbox_packets(sub: Path) -> list[Path]:
    return iter_packets(sub / GROUP_DOCS / "outbox")


def sub_inbox_dir(sub: Path) -> Path:
    return sub / GROUP_DOCS / "inbox"


def iter_snapshot_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.is_dir() and p.name.startswith("protocol-snapshot-")
    )


def iter_loose_packets(directory: Path) -> list[Path]:
    """Top-level .md files only (not inside snapshot dirs)."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.md") if p.is_file())



def deliver_head_to_sub(head: Path, manifest: dict, dry_run: bool) -> list[str]:
    log: list[str] = []
    for sub in manifest.get("subordinates", []):
        sub_id = sub.get("id", "")
        sub_path = Path(sub.get("path", ""))
        if not sub_id or not sub_path.is_dir():
            log.append(f"[SKIP] subordinate {sub_id}: path not found")
            continue
        outbox_sub = head / GROUP_DOCS / "outbox" / sub_id
        dest_parent = sub_inbox_dir(sub_path)
        for snap in iter_snapshot_dirs(outbox_sub):
            dest = dest_parent / snap.name
            log.append(f"HEAD->SUB {sub_id} [dir]: {snap.name} -> {dest}")
            if not dry_run:
                dest_parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(snap), str(dest))
        for packet in iter_loose_packets(outbox_sub):
            dest = dest_parent / packet.name
            log.append(f"HEAD->SUB {sub_id}: {packet.name} -> {dest}")
            if not dry_run:
                dest_parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(packet), str(dest))
    return log


def deliver_sub_to_head(sub: Path, manifest: dict, dry_run: bool) -> list[str]:
    log: list[str] = []
    head_info = manifest.get("head", {})
    head_id = head_info.get("id", "")
    head_path = Path(head_info.get("path", ""))
    if not head_path.is_dir():
        log.append(f"[SKIP] head {head_id}: path not found")
        return log

    sub_id = manifest.get("id") or manifest.get("module_id", "")
    if not sub_id:
        log.append("[SKIP] sub manifest: missing top-level 'id' (module id for head inbox/)")
        return log

    outbox = sub / GROUP_DOCS / "outbox"
    dest_parent = head_inbox_dir(head_path, sub_id)
    for snap in iter_snapshot_dirs(outbox):
        dest = dest_parent / snap.name
        log.append(f"SUB->HEAD {sub_id} [dir]: {snap.name} -> {dest}")
        if not dry_run:
            dest_parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(snap), str(dest))
    for packet in iter_loose_packets(outbox):
        dest = dest_parent / packet.name
        log.append(f"SUB->HEAD {sub_id}: {packet.name} -> {dest}")
        if not dry_run:
            dest_parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(packet), str(dest))
    return log


def deliver(repo: Path, dry_run: bool) -> int:
    manifest = load_manifest(repo)
    if not manifest:
        print(f"No group.manifest.yaml in {repo}", file=sys.stderr)
        return 2

    role = manifest.get("role", "")
    repo = _norm(repo)
    lines: list[str] = []

    if role == "head":
        lines = deliver_head_to_sub(repo, manifest, dry_run)
    elif role == "subordinate":
        lines = deliver_sub_to_head(repo, manifest, dry_run)
    else:
        print(f"Unknown role in manifest: {role!r} (expected head|subordinate)", file=sys.stderr)
        return 2

    if not lines:
        print("No packets to deliver.")
        return 0

    for line in lines:
        prefix = "[DRY-RUN] " if dry_run else ""
        print(f"{prefix}{line}")

    moved = sum(1 for l in lines if not l.startswith("[SKIP]"))
    print(f"\n{'Would deliver' if dry_run else 'Delivered'}: {moved} packet(s)")
    return 0


def status(repo: Path) -> int:
    manifest = load_manifest(repo)
    repo = _norm(repo)
    role = manifest.get("role", "?") if manifest else "?"

    print(f"sync-relay status: {repo}")
    print(f"  role: {role}")

    def report(label: str, packets: list[Path]) -> None:
        if packets:
            print(f"  {label}: {len(packets)} file(s)")
            for p in packets:
                print(f"    - {p.relative_to(repo)}")
        else:
            print(f"  {label}: (empty)")

    if role == "head":
        all_out, all_in = [], []
        for sub in (manifest or {}).get("subordinates", []):
            sub_id = sub.get("id", "?")
            out_dir = repo / GROUP_DOCS / "outbox" / sub_id
            out = iter_loose_packets(out_dir)
            snaps = iter_snapshot_dirs(out_dir)
            inn = iter_loose_packets(head_inbox_dir(repo, sub_id))
            if out or snaps:
                print(f"  outbox/{sub_id}: {len(out)} md, {len(snaps)} snapshot(s)")
                for p in out:
                    print(f"    - {p.relative_to(repo)}")
                for p in snaps:
                    print(f"    - {p.relative_to(repo)}/")
            if inn:
                print(f"  inbox/{sub_id}: {len(inn)} md")
                for p in inn:
                    print(f"    - {p.relative_to(repo)}")
            all_out.extend(out)
            all_in.extend(inn)
        if not all_out and not all_in:
            print("  outbox/inbox: (empty)")
    elif role == "subordinate":
        out_dir = repo / GROUP_DOCS / "outbox"
        report("outbox md", iter_loose_packets(out_dir))
        snaps = iter_snapshot_dirs(out_dir)
        if snaps:
            print(f"  outbox snapshots: {len(snaps)}")
            for p in snaps:
                print(f"    - {p.relative_to(repo)}/")
        report("inbox md", iter_loose_packets(sub_inbox_dir(repo)))
        in_snaps = iter_snapshot_dirs(sub_inbox_dir(repo))
        if in_snaps:
            print(f"  inbox snapshots: {len(in_snaps)}")
            for p in in_snaps:
                print(f"    - {p.relative_to(repo)}/")
    else:
        # Standalone or unknown — show local group dirs if any
        for name in ("inbox", "outbox"):
            report(name, iter_packets(repo / GROUP_DOCS / name))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync packet relay Head <-> Sub")
    parser.add_argument("--repo", type=Path, required=True, help="Sender repository path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deliver", action="store_true")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="With --deliver: show only")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        return 2

    if args.status:
        return status(repo)
    return deliver(repo, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
