"""Serialize a LayoutPlan to ``layout_plan.json`` for the ExtendScript executor."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .planner import LayoutPlan


def build_layout_plan_dict(plan: LayoutPlan) -> dict[str, Any]:
    """Serialize ``plan`` into a JSON-ready dict."""

    data = asdict(plan)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    return data


def write_layout_plan(plan: LayoutPlan, path: Path) -> None:
    """Write ``build_layout_plan_dict(plan)`` as pretty-printed JSON to ``path``."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_layout_plan_dict(plan)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
