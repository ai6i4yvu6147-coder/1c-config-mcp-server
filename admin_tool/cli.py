"""Admin Hub thin CLI (protocol v1.0.3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.cli_json import write_json_stdout
from shared.hub_protocol import run_apply_registry, run_export_registry, run_inventory, run_status

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
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument(
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
        "--json",
        action="store_true",
        default=True,
        help="JSON output on stdout (default: true)",
    )

    return parser


def _emit_json(payload: object, use_json: bool) -> None:
    indent = 2 if use_json else None
    write_json_stdout(payload, indent=indent)


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
        elif command == "apply-registry":
            payload = run_apply_registry(args.input, args.root, apply_mode=args.apply_mode)
            if not payload.get("success"):
                _emit_json(payload, args.json)
                if payload.get("errors"):
                    return EXIT_VALIDATION
                return EXIT_RUNTIME
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            return EXIT_VALIDATION
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
    raise SystemExit(main())
