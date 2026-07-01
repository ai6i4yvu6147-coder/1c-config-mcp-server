#!/usr/bin/env python3
"""
Protocol snapshot export/install for Head -> Sub baseline sync.

Usage:
  python protocol-snapshot.py --export --repo <head> --sub <sub-id> [--epoch N]
  python protocol-snapshot.py --attach-review --repo <head> --sub <sub-id> --files <path> [<path> ...]
  python protocol-snapshot.py --install --repo <sub>
  python protocol-snapshot.py --status --repo <path>
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

GROUP = Path("docs/group")
SHARED_CANDIDATES = (
    GROUP / "shared",
    Path("docs/admin-hub"),
)
PROTOCOL_GLOBS = ("protocol*.md", "registry-mapping*.md", "README.md")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _find_shared(repo: Path) -> Path | None:
    for cand in SHARED_CANDIDATES:
        if cand.is_dir() and any(cand.glob("protocol*.md")):
            return cand
    return None


def _collect_protocol_files(shared: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in PROTOCOL_GLOBS:
        files.extend(shared.glob(pattern))
    return sorted(set(files))


def _read_epoch(repo: Path) -> int:
    readme = GROUP / "README.md"
    if readme.is_file() and yaml is not None:
        text = readme.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "protocol_epoch" in line and "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts and parts[-1].isdigit():
                    return int(parts[-1])
    return 1


def _manifest_head(repo: Path) -> dict | None:
    if yaml is None:
        return None
    p = repo / "group.manifest.yaml"
    if not p.is_file():
        return None
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def cmd_export(repo: Path, sub_id: str, epoch: int | None) -> int:
    shared = _find_shared(repo)
    if not shared:
        print(f"No protocol source in {repo} (expected docs/group/shared or docs/admin-hub)", file=sys.stderr)
        return 2

    ep = epoch if epoch is not None else _read_epoch(repo)
    ts = _utc_ts()
    dest_name = f"protocol-snapshot-epoch{ep}-{ts}"
    outbox = repo / GROUP / "outbox" / sub_id / dest_name
    outbox.mkdir(parents=True, exist_ok=True)

    files = _collect_protocol_files(shared)
    if not files:
        print("No protocol files found to export", file=sys.stderr)
        return 2

    manifest = _manifest_head(repo)
    head_id = (manifest or {}).get("group", {}).get("id", repo.name)

    entries = []
    for src in files:
        rel = src.name
        dst = outbox / rel
        shutil.copy2(src, dst)
        entries.append({"path": rel, "sha256": _sha256(dst)})

    snap = {
        "snapshot_version": 1,
        "epoch": ep,
        "from": head_id,
        "to": sub_id,
        "created": ts,
        "files": entries,
    }
    snap_path = outbox / "SNAPSHOT.yaml"
    if yaml is None:
        print("PyYAML required for SNAPSHOT.yaml", file=sys.stderr)
        return 2
    with snap_path.open("w", encoding="utf-8") as f:
        yaml.dump(snap, f, allow_unicode=True, default_flow_style=False)

    print(f"Exported {len(entries)} file(s) to {outbox}")
    return 0


def cmd_attach_review(repo: Path, sub_id: str, file_paths: list[str]) -> int:
    if not file_paths:
        print("--files required for attach-review", file=sys.stderr)
        return 2

    ts = _utc_ts()
    dest_name = f"review-snapshot-{ts}"
    outbox = repo / GROUP / "outbox" / sub_id / dest_name
    outbox.mkdir(parents=True, exist_ok=True)

    copied = 0
    for rel in file_paths:
        src = (repo / rel).resolve()
        if not src.is_file():
            print(f"[SKIP] not a file: {rel}", file=sys.stderr)
            continue
        try:
            src.relative_to(repo.resolve())
        except ValueError:
            print(f"[SKIP] outside repo: {rel}", file=sys.stderr)
            continue
        dst = outbox / src.name
        shutil.copy2(src, dst)
        copied += 1

    if copied == 0:
        print("No files copied", file=sys.stderr)
        return 2

    print(f"Attached {copied} file(s) to {outbox}")
    return 0


def _find_inbox_snapshot(repo: Path) -> Path | None:
    inbox = repo / GROUP / "inbox"
    if not inbox.is_dir():
        return None
    candidates = sorted(
        (p for p in inbox.iterdir() if p.is_dir() and p.name.startswith("protocol-snapshot-")),
        key=lambda p: p.name,
    )
    return candidates[-1] if candidates else None


def cmd_install(repo: Path) -> int:
    snap_dir = _find_inbox_snapshot(repo)
    if not snap_dir:
        print("No protocol-snapshot-* directory in docs/group/inbox/", file=sys.stderr)
        return 2

    snap_file = snap_dir / "SNAPSHOT.yaml"
    if not snap_file.is_file() or yaml is None:
        print("SNAPSHOT.yaml missing or PyYAML not installed", file=sys.stderr)
        return 2

    with snap_file.open(encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    epoch = meta.get("epoch", 1)
    dest_root = repo / GROUP / "protocol-ref" / f"epoch{epoch}"
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    count = 0
    for item in snap_dir.iterdir():
        if item.name == "SNAPSHOT.yaml":
            shutil.copy2(item, dest_root / item.name)
            continue
        if item.is_file():
            shutil.copy2(item, dest_root / item.name)
            count += 1

    print(f"Installed {count} protocol file(s) to {dest_root}")
    return 0


def cmd_status(repo: Path) -> int:
    print(f"protocol-snapshot status: {repo}")
    shared = _find_shared(repo)
    print(f"  shared source: {shared or '(none)'}")

    ref = repo / GROUP / "protocol-ref"
    if ref.is_dir():
        for d in sorted(ref.iterdir()):
            if d.is_dir():
                n = sum(1 for f in d.iterdir() if f.is_file())
                print(f"  protocol-ref/{d.name}: {n} file(s)")
    else:
        print("  protocol-ref: (none)")

    snap = _find_inbox_snapshot(repo)
    if snap:
        print(f"  inbox pending: {snap.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Protocol snapshot export/install")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--sub", help="Sub module id (export / attach-review)")
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--files", nargs="+", help="Paths to copy into review-snapshot (attach-review)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--export", action="store_true")
    group.add_argument("--attach-review", action="store_true")
    group.add_argument("--install", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"Not a directory: {repo}", file=sys.stderr)
        return 2

    if args.export:
        if not args.sub:
            print("--sub required for export", file=sys.stderr)
            return 2
        return cmd_export(repo, args.sub, args.epoch)
    if args.attach_review:
        if not args.sub:
            print("--sub required for attach-review", file=sys.stderr)
            return 2
        return cmd_attach_review(repo, args.sub, args.files or [])
    if args.install:
        return cmd_install(repo)
    return cmd_status(repo)


if __name__ == "__main__":
    sys.exit(main())
