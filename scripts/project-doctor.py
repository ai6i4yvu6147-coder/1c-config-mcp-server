#!/usr/bin/env python3
"""
Проверка репозитория на соответствие канонам (2.5.3). Типы: S, H, Sub.

Usage:
  python project-doctor.py
  python project-doctor.py --repo <path> --type S|H|Sub
  python project-doctor.py --repo <path> --wi <path-to-workspace-improve> --heal
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
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
    "docs/agent-map.md",
    "docs/architecture.md",
    "docs/todo.md",
]

REQUIRED: dict[str, list[str]] = {
    "S": BASE.copy(),
    "H": BASE
    + [
        "group.manifest.yaml",
        "GROUP-HUB.md",
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

# Paths a normalize pass materializes verbatim from WI — safe to auto-heal
# by byte-copy, since there is exactly one correct answer (WI's own copy).
CANON_HEAL_GLOB = "docs/canons/*.md"

# .cursor/commands/re-normalize.md is WI-templated per role (cursor_commands in
# normalize.bundle.yaml); everything else in .cursor/commands/ stays project-local.
ROLE_TEMPLATE_DIR = {"S": "standalone", "H": "head", "Sub": "subordinate"}
RE_NORMALIZE_REL = Path(".cursor/commands/re-normalize.md")

# Universal .cursor/rules/* — identical across every role (cursor_rules in
# normalize.bundle.yaml). Any other rule file in a repo stays project-local.
UNIVERSAL_RULE_NAMES = ("docs-in-english.mdc", "keep-repo-current.mdc", "prompt-authoring.mdc")

# Paths that carry the negotiated/normalized cluster state. A dirty working
# tree here means "applied locally, not committed" — flagged, never auto-fixed
# (committing is a human/agent judgment call, not a mechanical one).
CANON_MANAGED_GIT_PATHS = [
    "docs/canons",
    "group.manifest.yaml",
    "docs/group/protocol-ref",
    "docs/group/shared",
    "GROUP-HUB.md",
]


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


def _parse_frontmatter(path: Path) -> tuple[dict | None, str | None]:
    """(data, error). data is parsed frontmatter, or {'_raw': str} when PyYAML is absent."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None, "no frontmatter (must start with ---)"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "unterminated frontmatter"
    fm = parts[1]
    if yaml is None:
        return {"_raw": fm}, None
    try:
        data = yaml.safe_load(fm)
    except Exception as exc:  # noqa: BLE001 — report any YAML error as a finding
        return None, f"invalid YAML frontmatter ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


def _parse_agent_frontmatter(path: Path) -> tuple[dict | None, str | None]:
    """Parse agent frontmatter; fall back to line-based extraction when strict YAML fails.

    Cursor accepts single-line descriptions with colons; PyYAML does not. Per Cursor docs,
    that frontmatter is valid — do not treat ScannerError as an agent defect.
    """
    data, err = _parse_frontmatter(path)
    if data is not None or err is None:
        return data, err
    if "invalid YAML" not in (err or ""):
        return data, err

    text = path.read_text(encoding="utf-8", errors="replace")
    fm = text.split("---", 2)[1]
    fallback: dict = {"_lenient": True}
    for key in ("name", "model", "description", "readonly"):
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", fm, re.MULTILINE)
        if m:
            val = m.group(1).strip()
            if key == "readonly":
                fallback[key] = val.lower() in ("true", "yes")
            else:
                fallback[key] = val
    if not fallback.get("name"):
        fallback["name"] = path.stem
    if fallback.get("name") or fallback.get("description") or fallback.get("model"):
        return fallback, None
    return data, err


def _bad_model_slug(model: object) -> bool:
    s = str(model)
    return "[]" in s or s != s.strip() or " " in s


def _check_entities(repo: Path) -> list[str]:
    """Validate materialized .cursor/ agents and skills frontmatter (catches copy corruption)."""
    errors: list[str] = []

    for p in sorted((repo / ".cursor/agents").glob("*.md")):
        data, err = _parse_agent_frontmatter(p)
        if err:
            errors.append(f"AGENT {p.name}: {err}")
            continue
        if "_raw" in data:  # no PyYAML — text-level check only
            if "[]" in data["_raw"]:
                errors.append(f"AGENT {p.name}: '[]' in frontmatter (corrupted slug)")
            continue
        if not data.get("name"):
            errors.append(f"AGENT {p.name}: missing name")
        desc = data.get("description")
        if not (isinstance(desc, str) and desc.strip()):
            errors.append(f"AGENT {p.name}: empty description")
        if "model" in data and _bad_model_slug(data["model"]):
            errors.append(f"AGENT {p.name}: bad model slug {data['model']!r}")

    for p in sorted((repo / ".cursor/skills").glob("*/SKILL.md")):
        data, err = _parse_frontmatter(p)
        if err:
            errors.append(f"SKILL {p.parent.name}: {err}")
            continue
        if "_raw" in data:
            continue
        if not data.get("name"):
            errors.append(f"SKILL {p.parent.name}: missing name")
        desc = data.get("description")
        if not (isinstance(desc, str) and desc.strip()):
            errors.append(f"SKILL {p.parent.name}: empty description")

    return errors


def _run_git(repo: Path, *args: str) -> str | None:
    """Run git in repo; return stripped stdout, or None if git/repo unavailable."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _check_canon_fidelity(repo: Path, wi: Path | None, heal: bool) -> tuple[list[str], list[str]]:
    """Compare docs/canons/*.md against the WI source. Auto-healable: exactly one correct
    answer exists (WI's own file), so a mismatch is mechanical drift, not a judgment call."""
    warnings: list[str] = []
    healed: list[str] = []
    if wi is None:
        return warnings, healed

    wi_canons = wi / "docs" / "canons"
    if not wi_canons.is_dir():
        return warnings, healed

    for wi_file in sorted(wi_canons.glob("*.md")):
        rel = Path("docs/canons") / wi_file.name
        local = repo / rel
        wi_bytes = wi_file.read_bytes()
        if not local.is_file():
            if heal:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(wi_bytes)
                healed.append(f"HEALED: added missing {rel} (copied from WI)")
            else:
                warnings.append(f"WARN: missing {rel} (present in WI source)")
            continue
        if local.read_bytes() != wi_bytes:
            if heal:
                local.write_bytes(wi_bytes)
                healed.append(f"HEALED: {rel} was stale vs WI source — overwritten")
            else:
                warnings.append(
                    f"WARN: {rel} differs from WI source (stale canon copy; re-normalize or --heal)"
                )

    return warnings, healed


def _check_universal_rules(repo: Path, wi: Path | None, heal: bool) -> tuple[list[str], list[str]]:
    """The 3 rules in <WI>/templates/cursor-rules/ are identical across every role —
    same mechanical byte-copy logic as canon docs, no role-keying needed."""
    warnings: list[str] = []
    healed: list[str] = []
    if wi is None:
        return warnings, healed

    wi_rules_dir = wi / "templates" / "cursor-rules"
    if not wi_rules_dir.is_dir():
        return warnings, healed

    for name in UNIVERSAL_RULE_NAMES:
        wi_file = wi_rules_dir / name
        if not wi_file.is_file():
            continue  # older WI without this rule yet — nothing to check
        rel = Path(".cursor/rules") / name
        local = repo / rel
        wi_bytes = wi_file.read_bytes()
        if not local.is_file():
            if heal:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(wi_bytes)
                healed.append(f"HEALED: added missing {rel} (copied from WI)")
            else:
                warnings.append(f"WARN: missing {rel} (universal WI rule)")
            continue
        if local.read_bytes() != wi_bytes:
            if heal:
                local.write_bytes(wi_bytes)
                healed.append(f"HEALED: {rel} was stale vs WI source — overwritten")
            else:
                warnings.append(f"WARN: {rel} differs from WI source (stale universal rule; re-normalize or --heal)")

    return warnings, healed


def _check_command_fidelity(
    repo: Path, repo_type: str, wi: Path | None, heal: bool
) -> tuple[list[str], list[str]]:
    """`.cursor/commands/re-normalize.md` is the one WI-templated command (role-specific
    source) — same mechanical byte-copy logic as canon docs, just role-keyed instead of
    a single shared source."""
    warnings: list[str] = []
    healed: list[str] = []
    if wi is None:
        return warnings, healed

    role_dir = ROLE_TEMPLATE_DIR.get(repo_type)
    if role_dir is None:
        return warnings, healed

    wi_template = wi / "templates" / role_dir / "commands-re-normalize.md"
    if not wi_template.is_file():
        return warnings, healed  # older WI without this template yet — nothing to check

    local = repo / RE_NORMALIZE_REL
    wi_bytes = wi_template.read_bytes()
    if not local.is_file():
        if heal:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(wi_bytes)
            healed.append(f"HEALED: added missing {RE_NORMALIZE_REL} (copied from WI, role {repo_type})")
        else:
            warnings.append(f"WARN: missing {RE_NORMALIZE_REL} (WI has a {repo_type} template for it)")
        return warnings, healed

    if local.read_bytes() != wi_bytes:
        if heal:
            local.write_bytes(wi_bytes)
            healed.append(f"HEALED: {RE_NORMALIZE_REL} was stale vs WI's {repo_type} template — overwritten")
        else:
            warnings.append(
                f"WARN: {RE_NORMALIZE_REL} differs from WI's {repo_type} template (stale; re-normalize or --heal)"
            )

    return warnings, healed


def _check_cursor_tracked(repo: Path, heal: bool) -> tuple[list[str], list[str]]:
    """.cursor/ is the materialized governance layer — if git never tracked it, a lost
    working copy silently erases it with no history to recover from. Staging it is
    mechanical (one correct action, no content decision); heal never commits."""
    warnings: list[str] = []
    healed: list[str] = []
    cursor_dir = repo / ".cursor"
    if not cursor_dir.is_dir():
        return warnings, healed
    if _run_git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return warnings, healed

    tracked = _run_git(repo, "ls-files", ".cursor")
    has_any_files = any(cursor_dir.rglob("*.md")) or any(cursor_dir.rglob("*.mdc"))
    if has_any_files and not tracked:
        if heal:
            _run_git(repo, "add", ".cursor")
            healed.append("HEALED: staged .cursor/ (was fully untracked) — commit still required")
        else:
            warnings.append("WARN: .cursor/ has files but none are tracked by git (git add .cursor)")

    return warnings, healed


def _check_rule_hygiene(repo: Path) -> list[str]:
    """Flag-only, project-local rules only: whether to fix the format or retire the rule
    is a judgment call, not something to silently rewrite. Universal rules are handled
    (and auto-healed) separately by _check_universal_rules."""
    warnings: list[str] = []
    rules_dir = repo / ".cursor" / "rules"
    if not rules_dir.is_dir():
        return warnings

    for p in sorted(rules_dir.iterdir()):
        if not p.is_file() or p.name in UNIVERSAL_RULE_NAMES:
            continue
        if p.suffix != ".mdc":
            warnings.append(
                f"WARN: .cursor/rules/{p.name} is not .mdc — Cursor likely won't load it as a rule"
            )
            continue
        data, err = _parse_frontmatter(p)
        if err:
            warnings.append(f"WARN: .cursor/rules/{p.name}: {err} — may not load as a Cursor rule")
        if p.stem.isdigit():
            warnings.append(
                f"WARN: .cursor/rules/{p.name} has a non-descriptive name — rename to what it does"
            )

    return warnings


def _check_canon_paths_clean(repo: Path) -> list[str]:
    """Flag-only: whether/when to commit is the operator's call (see normalize-governance.md).
    This just makes the state visible instead of requiring a manual `git status` per repo."""
    warnings: list[str] = []
    if _run_git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return warnings

    existing = [p for p in CANON_MANAGED_GIT_PATHS if (repo / p).exists()]
    if not existing:
        return warnings
    status = _run_git(repo, "status", "--porcelain", "--", *existing)
    if status:
        n = len(status.splitlines())
        warnings.append(
            f"WARN: {n} uncommitted change(s) under canon-managed paths "
            f"({', '.join(existing)}) — registry state may not match git history"
        )
    return warnings


def check_repo(
    repo: Path, repo_type: str, wi: Path | None = None, heal: bool = False
) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    healed: list[str] = []

    for rel in REQUIRED.get(repo_type, BASE):
        if not (repo / rel).exists():
            errors.append(f"MISSING [{repo_type}]: {rel}")

    for name in FORBIDDEN_ROOT:
        if (repo / name).exists():
            errors.append(f"FORBIDDEN in root: {name}")

    errors.extend(_check_entities(repo))

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
    if gi.is_file() and ".tasks/" not in gi.read_text(encoding="utf-8", errors="replace"):
        warnings.append("WARN: add .tasks/ to .gitignore (subagent handoff artifacts)")

    if repo_type == "Sub":
        if not (repo / "group.manifest.yaml").exists():
            warnings.append("WARN: recommended group.manifest.yaml")
        for field in _integration_has_fields(repo):
            warnings.append(f"WARN: integration.md missing field {field}")

    if not (repo / "docs/canons/normalize-governance.md").exists():
        warnings.append("WARN: missing docs/canons/normalize-governance.md")

    if not (repo / "tests").exists():
        warnings.append("WARN: recommended tests/")

    # --- healing checks (mechanical auto-fix when --heal; otherwise flag-only) ---
    fidelity_warnings, fidelity_healed = _check_canon_fidelity(repo, wi, heal)
    warnings.extend(fidelity_warnings)
    healed.extend(fidelity_healed)

    command_warnings, command_healed = _check_command_fidelity(repo, repo_type, wi, heal)
    warnings.extend(command_warnings)
    healed.extend(command_healed)

    rule_warnings, rule_healed = _check_universal_rules(repo, wi, heal)
    warnings.extend(rule_warnings)
    healed.extend(rule_healed)

    cursor_warnings, cursor_healed = _check_cursor_tracked(repo, heal)
    warnings.extend(cursor_warnings)
    healed.extend(cursor_healed)

    # --- flag-only checks (never auto-fixed: judgment calls, not mechanical) ---
    warnings.extend(_check_rule_hygiene(repo))
    warnings.extend(_check_canon_paths_clean(repo))

    return errors, warnings, healed


def main() -> int:
    parser = argparse.ArgumentParser(description="Project structure canon checker")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--type", choices=["S", "H", "Sub"])
    parser.add_argument(
        "--wi",
        type=Path,
        default=None,
        help="Path to Workspace improve, for canon content-fidelity check "
        "(falls back to $WORKSPACE_IMPROVE env var)",
    )
    parser.add_argument(
        "--heal",
        action="store_true",
        help="Auto-fix mechanical drift (stale canon files, untracked .cursor/). "
        "Never commits. Judgment-call findings (rule hygiene, uncommitted canon "
        "paths) are always flag-only.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    repo_type = args.type or detect_type(repo)
    wi_env = os.environ.get("WORKSPACE_IMPROVE")
    wi = (args.wi or (Path(wi_env) if wi_env else None))
    if wi is not None:
        wi = wi.resolve()
        if wi == repo:
            wi = None  # WI checking itself — no external source to compare against

    print(f"project-doctor: {repo}")
    print(f"  type: {repo_type} (canon 2.5.3)")

    errors, warnings, healed = check_repo(repo, repo_type, wi=wi, heal=args.heal)

    for line in errors:
        print(f"  [FAIL] {line}")
    for line in healed:
        print(f"  [{line}" if line.startswith("HEALED") else f"  {line}")
    for line in warnings:
        print(f"  {line}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s), {len(healed)} healed, {len(warnings)} warning(s)")
        return 1
    print(f"\nOK ({len(healed)} healed, {len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
