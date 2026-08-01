"""Admin Hub thin CLI (protocol v1.0.3)."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.agent_guide import GuideError, GuideSectionError, envelope as guide_envelope
from shared.cli_json import write_json_stdout
from shared.hub_protocol import run_apply_registry, run_export_registry, run_inventory, run_status
from shared.hub_rebuild import (
    run_rebuild_all,
    run_rebuild_index,
    run_reconcile_markers,
    run_triggered_rebuilds,
)
from shared.runtime_paths import get_paths
from shared.tool_calls_log import READ_DEFAULT_LIMIT, read_tool_calls, tool_calls_db_path

EXIT_SUCCESS = 0
EXIT_VALIDATION = 1
EXIT_IO = 2
EXIT_RUNTIME = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="1c-config-cli",
        description="1C Config MCP — Admin Hub protocol CLI",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Portable module root (overrides CONFIG_MCP_ROOT and auto-detect)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("inventory", "Module inventory (JSON)"),
        ("status", "Module status and readiness (JSON)"),
        ("export-registry", "Export registry fragment (JSON)"),
        ("rebuild-all", "Rebuild all databases with valid source (JSON)"),
        ("reconcile-markers", "Remove stale build markers and orphaned .tmp (JSON)"),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument(
            "--json",
            action="store_true",
            default=True,
            help="JSON output on stdout (default: true)",
        )

    rebuild_sp = sub.add_parser("rebuild-index", help="Rebuild one database index (JSON)")
    rebuild_sp.add_argument(
        "--db-id",
        required=True,
        help="infobaseId (database registry id)",
    )
    rebuild_sp.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON output on stdout (default: true)",
    )

    apply_sp = sub.add_parser("apply-registry", help="Apply registry fragment (JSON)")
    apply_sp.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to registry fragment or export JSON",
    )
    apply_sp.add_argument(
        "--apply-mode",
        choices=("patch", "snapshot"),
        default="patch",
        help="Apply mode: patch (upsert-only, default) or snapshot",
    )
    apply_sp.add_argument(
        "--trigger-rebuild",
        action="store_true",
        help="Run rebuild-index for each followUpOperations entry after apply",
    )
    apply_sp.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON output on stdout (default: true)",
    )

    guide_sp = sub.add_parser("guide", help="Agent guide shipped with this module (JSON)")
    guide_sp.add_argument(
        "--section",
        default=None,
        help="Section id from the guide menu; 'all' for the whole text (default: overview)",
    )
    guide_sp.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON output on stdout (default: true)",
    )

    calls_sp = sub.add_parser("tool-calls", help="Read tool-call journal rows (JSON)")
    calls_sp.add_argument("--task-id", default=None, help="Filter by task_id (exact)")
    calls_sp.add_argument("--session-id", default=None, help="Filter by session_id (exact)")
    calls_sp.add_argument("--tool", default=None, help="Filter by tool name (exact)")
    calls_sp.add_argument("--since", default=None, help="Keep rows with ts_utc >= SINCE (ISO-8601 Z)")
    calls_sp.add_argument("--until", default=None, help="Keep rows with ts_utc <= UNTIL (ISO-8601 Z)")
    calls_sp.add_argument("--only-errors", action="store_true", help="Only failed calls (success = 0)")
    calls_sp.add_argument(
        "--limit",
        type=int,
        default=READ_DEFAULT_LIMIT,
        help=f"Max rows, newest first (default: {READ_DEFAULT_LIMIT})",
    )
    calls_sp.add_argument("--offset", type=int, default=0, help="Rows to skip (pagination)")
    calls_sp.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON output on stdout (default: true)",
    )

    return parser


def run_guide(args: argparse.Namespace) -> dict:
    """Agent guide envelope — same markdown the MCP `guide` tool returns, plus module identity."""
    paths = get_paths(args.root)
    return guide_envelope(
        args.section,
        module=paths.module_id,
        module_type=paths.module_type,
        module_version=paths.module_version,
    )


def run_tool_calls(args: argparse.Namespace) -> dict:
    """Read the module's tool-call journal into a Hub-uniform JSON envelope."""
    paths = get_paths(args.root)
    db_path = tool_calls_db_path(paths.logs_dir)
    rows = read_tool_calls(
        db_path,
        task_id=args.task_id,
        session_id=args.session_id,
        tool=args.tool,
        since=args.since,
        until=args.until,
        only_errors=args.only_errors,
        limit=args.limit,
        offset=args.offset,
    )
    return {
        "module": paths.module_id,
        "moduleType": paths.module_type,
        "db": str(db_path),
        "query": {
            "taskId": args.task_id,
            "sessionId": args.session_id,
            "tool": args.tool,
            "since": args.since,
            "until": args.until,
            "onlyErrors": bool(args.only_errors),
            "limit": args.limit,
            "offset": args.offset,
        },
        "count": len(rows),
        "rows": rows,
    }


def _emit_json(payload: object, use_json: bool) -> None:
    indent = 2 if use_json else None
    write_json_stdout(payload, indent=indent)


def _rebuild_exit_code(payload: dict) -> int:
    if payload.get("success"):
        return EXIT_SUCCESS
    if payload.get("result") == "busy":
        return EXIT_RUNTIME
    if payload.get("errors") and any(
        "not found" in e.lower() for e in payload["errors"]
    ):
        return EXIT_VALIDATION
    return EXIT_RUNTIME


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = args.command

    try:
        if command == "inventory":
            payload = run_inventory(args.root)
        elif command == "status":
            payload = run_status(args.root)
        elif command == "export-registry":
            payload = run_export_registry(args.root)
        elif command == "rebuild-index":
            payload = run_rebuild_index(args.db_id, args.root)
            _emit_json(payload, args.json)
            return _rebuild_exit_code(payload)
        elif command == "rebuild-all":
            payload = run_rebuild_all(args.root)
            _emit_json(payload, args.json)
            return EXIT_SUCCESS if payload.get("success") else EXIT_RUNTIME
        elif command == "reconcile-markers":
            payload = run_reconcile_markers(args.root)
        elif command == "guide":
            payload = run_guide(args)
        elif command == "tool-calls":
            payload = run_tool_calls(args)
        elif command == "apply-registry":
            payload = run_apply_registry(args.input, args.root, apply_mode=args.apply_mode)
            if payload.get("success") and args.trigger_rebuild:
                follow_ups = (
                    payload.get("postApplyActions") or {}
                ).get("followUpOperations") or []
                payload["triggeredRebuilds"] = run_triggered_rebuilds(
                    follow_ups, explicit_root=args.root
                )
            if not payload.get("success"):
                _emit_json(payload, args.json)
                if payload.get("errors"):
                    return EXIT_VALIDATION
                return EXIT_RUNTIME
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            return EXIT_VALIDATION
    except GuideSectionError as exc:
        # Unknown section is a bad argument, not a broken module.
        print(str(exc), file=sys.stderr)
        return EXIT_VALIDATION
    except GuideError as exc:
        # Guide did not ship — a packaging problem, same class as a missing file.
        print(str(exc), file=sys.stderr)
        return EXIT_IO
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_IO
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_IO
    except json.JSONDecodeError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_VALIDATION
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_VALIDATION
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME

    _emit_json(payload, args.json)

    return EXIT_SUCCESS


if __name__ == "__main__":
    # Required on Windows for the PyInstaller-frozen build: without it, every spawned
    # ProcessPoolExecutor worker (P-8 parallel form parsing) would re-launch the whole CLI
    # instead of running as a plain worker process.
    multiprocessing.freeze_support()
    raise SystemExit(main())
