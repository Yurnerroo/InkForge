"""Command-line entry point for the Level 2 layout planner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .planner import build_layout_plan
from .planwriter import write_layout_plan
from .profile import ProfileError, resolve_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inkforge-plan",
        description=(
            "Read a Level 1 manifest.json and a newspaper profile, and produce "
            "layout_plan.json for the InDesign executor."
        ),
    )
    parser.add_argument("manifest", type=Path, help="Path to manifest.json (from inkforge-check)")
    parser.add_argument(
        "--profile",
        required=True,
        help=(
            "Newspaper profile id (looked up in --profiles-dir as <id>.yaml) "
            "or a direct path to a profile .yaml file"
        ),
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("profiles"),
        help="Directory containing per-newspaper profile .yaml files (default: ./profiles)",
    )
    parser.add_argument(
        "--plan-out",
        type=Path,
        default=None,
        help="Where to write layout_plan.json (default: alongside the manifest)",
    )
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"Помилка: manifest.json не знайдено: {args.manifest}", file=sys.stderr)
        return 2

    try:
        profile = resolve_profile(args.profile, args.profiles_dir)
    except ProfileError as exc:
        print(f"Помилка профілю: {exc}", file=sys.stderr)
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_layout_plan(manifest, profile)

    print(f"Газета: {profile.display_name} ({profile.id})")
    print(f"Сторінок у плані: {len(plan.pages)}")
    for page in plan.pages:
        suffix = f" — {'; '.join(page.notes)}" if page.notes else ""
        print(f"  стор. {page.page}: {page.status}{suffix}")

    if plan.warnings:
        print("\nПопередження:")
        for warning in plan.warnings:
            print(f"  - {warning}")

    plan_path = args.plan_out or (args.manifest.parent / "layout_plan.json")
    write_layout_plan(plan, plan_path)
    print(f"\nlayout_plan.json записано у {plan_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
