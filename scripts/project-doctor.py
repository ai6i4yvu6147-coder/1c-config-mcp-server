#!/usr/bin/env python3
"""
Проверка репозитория на соответствие канонам (2.4.0). Типы: S, H, Sub.

Usage:
  python project-doctor.py
  python project-doctor.py --repo <path> --type S|H|Sub
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent

BASE = [
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/agent-onboarding.md",
    "docs/architecture.md",
    "docs/todo.md",
]

REQUIRED: dict[str, list[str]] = {
    "S": BASE.copy(),
    "H": BASE
    + [
        "group.manifest.yaml",
        "docs/group/README.md",
        "docs/group/shared",
    ],
    "Sub": BASE
    + [
        "docs/group/integration.md",
    ],
}

GROUP_SCRIPTS = ("protocol-snapshot.py", "sync-status.py")
INTEGRATION_FIELDS = (
    "protocol_epoch",
    "protocol_sync_state",
)

FORBIDDEN_ROOT = ["readme.txt"]


def _manifest_role(repo: Path) -> str | None:
    manifest = repo / "group.manifest.yaml"
    if not manifest.is_file() or yaml is None:
        return None
    with manifest.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("role")


def detect_type(repo: Path) -> str:
    role = _manifest_role(repo)
    if role == "head":
        return "H"
    if role == "subordinate":
        return "Sub"
    if (repo / "group.manifest.yaml").is_file() and (repo / "docs/group/shared").is_dir():
        return "H"
    if (repo / "docs/group/integration.md").is_file():
        return "Sub"
    return "S"


def _integration_has_fields(repo: Path) -> list[str]:
    missing: list[str] = []
    path = repo / "docs/group/integration.md"
    if not path.is_file():
        return missing
    text = path.read_text(encoding="utf-8", errors="replace")
    for field in INTEGRATION_FIELDS:
        if field not in text:
            missing.append(field)
    return missing


def check_repo(repo: Path, repo_type: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED.get(repo_type, BASE):
        if not (repo / rel).exists():
            errors.append(f"MISSING [{repo_type}]: {rel}")

    for name in FORBIDDEN_ROOT:
        if (repo / name).exists():
            errors.append(f"FORBIDDEN in root: {name}")

    if (repo / "templates").is_dir():
        is_wi_meta = (repo / "initiators").is_dir() and (repo / "normalize.bundle.yaml").is_file()
        if not is_wi_meta:
            warnings.append("WARN: templates/ в продуктовом репо — обычно только в WI")

    if (repo / "scripts/normalize-apply.py").is_file():
        errors.append("LEGACY: scripts/normalize-apply.py — удалить (normalize agent-first)")

    if repo_type in ("H", "Sub"):
        for script in GROUP_SCRIPTS:
            if not (repo / "scripts" / script).is_file():
                warnings.append(f"WARN: missing scripts/{script} (copy during normalize H/Sub)")
        gi = repo / ".gitignore"
        if gi.is_file() and "group/inbox" not in gi.read_text(encoding="utf-8", errors="replace"):
            warnings.append("WARN: add docs/group/inbox/ and outbox/ to .gitignore")

    if repo_type == "Sub":
        if not (repo / "group.manifest.yaml").exists():
            warnings.append("WARN: recommended group.manifest.yaml")
        for field in _integration_has_fields(repo):
            warnings.append(f"WARN: integration.md missing field {field}")

    if not (repo / "docs/canons/normalize-governance.md").exists():
        warnings.append("WARN: missing docs/canons/normalize-governance.md")

    if not (repo / "tests").exists():
        warnings.append("WARN: recommended tests/")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Project structure canon checker")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--type", choices=["S", "H", "Sub"])
    args = parser.parse_args()

    repo = args.repo.resolve()
    repo_type = args.type or detect_type(repo)

    print(f"project-doctor: {repo}")
    print(f"  type: {repo_type} (canon 2.4.0)")

    errors, warnings = check_repo(repo, repo_type)

    for line in errors:
        print(f"  [FAIL] {line}")
    for line in warnings:
        print(f"  {line}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s)")
        return 1
    print(f"\nOK ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
