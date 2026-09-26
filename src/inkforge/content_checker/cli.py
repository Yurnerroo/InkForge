"""Command-line entry point for the Level 1 content checker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manifest import write_manifest
from .report import render_report
from .scanner import scan_issue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inkforge-check",
        description="Scan a weekly newspaper issue folder and report content issues.",
    )
    parser.add_argument("issue_folder", type=Path, help="Path to the weekly issue folder")
    parser.add_argument("--newspaper", default="", help="Newspaper name/title (for the report)")
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Where to write manifest.json (default: <issue_folder>/manifest.json)",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip writing manifest.json, only print the report",
    )
    args = parser.parse_args(argv)

    if not args.issue_folder.is_dir():
        print(f"Помилка: папку випуску не знайдено: {args.issue_folder}", file=sys.stderr)
        return 2

    issue = scan_issue(args.issue_folder, newspaper=args.newspaper)
    print(render_report(issue))

    if not args.no_manifest:
        manifest_path = args.manifest_out or (args.issue_folder / "manifest.json")
        write_manifest(issue, manifest_path)
        print(f"\nmanifest.json записано у {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
