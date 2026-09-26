"""FastAPI-застосунок Рівня 3 — One-Click Launcher.

Одна локальна сторінка з кнопками "Перевірити контент" / "Побудувати план
верстки" / "Зверстати в InDesign", кожна — окремий підтверджуваний крок (без
автоланцюжка). /api/check і /api/plan — тонкі обгортки над вже протестованим
кодом Рівня 1/2. /api/execute делегує в `indesign_bridge` (COM, лише Windows,
не перевірено на реальному InDesign). Див. docs/architecture.md, "Рівень 3".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..content_checker.manifest import build_manifest, write_manifest
from ..content_checker.scanner import scan_issue
from ..layout_engine.planner import build_layout_plan
from ..layout_engine.planwriter import write_layout_plan
from ..layout_engine.profile import ProfileError, resolve_profile
from . import indesign_bridge

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILES_DIR = REPO_ROOT / "profiles"
DEFAULT_SCRIPT_PATH = REPO_ROOT / "extendscript" / "inkforge_layout.jsx"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class IssueRequest(BaseModel):
    issue_folder: str
    profile: str


class ExecuteRequest(IssueRequest):
    indd_path: str
    issue_date: str | None = None
    issue_number: str | None = None


def list_profile_ids(profiles_dir: Path) -> list[str]:
    if not profiles_dir.is_dir():
        return []
    return sorted(path.stem for path in profiles_dir.glob("*.yaml"))


def create_app(
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    script_path: Path = DEFAULT_SCRIPT_PATH,
) -> FastAPI:
    """Build the launcher's FastAPI app.

    ``profiles_dir``/``script_path`` are overridable so tests can point at
    fixture directories instead of the real repo-level ``profiles/`` and
    ``extendscript/inkforge_layout.jsx``.
    """

    app = FastAPI(title="InkForge Launcher")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/api/profiles")
    def profiles() -> dict[str, Any]:
        return {"profiles": list_profile_ids(profiles_dir)}

    @app.post("/api/check")
    def check(req: IssueRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        if not issue_path.is_dir():
            raise HTTPException(400, f"Папку випуску не знайдено: {issue_path}")

        issue = scan_issue(issue_path, newspaper=req.profile)
        manifest = build_manifest(issue)
        write_manifest(issue, issue_path / "manifest.json")
        return {
            "manifest_path": str(issue_path / "manifest.json"),
            "warnings": manifest["warnings"],
            "pages": [
                {
                    "page": page["page"],
                    "articles": len(page["articles"]),
                    "warnings": page["folder_warnings"],
                }
                for page in manifest["pages"]
            ],
        }

    @app.post("/api/plan")
    def plan(req: IssueRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        manifest_path = issue_path / "manifest.json"
        if not manifest_path.is_file():
            raise HTTPException(
                400, "manifest.json не знайдено — спочатку запусти /api/check."
            )

        try:
            profile = resolve_profile(req.profile, profiles_dir)
        except ProfileError as exc:
            raise HTTPException(400, str(exc)) from exc

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layout_plan = build_layout_plan(manifest, profile)
        plan_path = issue_path / "layout_plan.json"
        write_layout_plan(layout_plan, plan_path)
        return {
            "plan_path": str(plan_path),
            "warnings": list(layout_plan.warnings),
            "pages": [
                {"page": page.page, "status": page.status, "notes": list(page.notes)}
                for page in layout_plan.pages
            ],
        }

    @app.post("/api/execute")
    def execute(req: ExecuteRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        plan_path = issue_path / "layout_plan.json"
        if not plan_path.is_file():
            raise HTTPException(
                400, "layout_plan.json не знайдено — спочатку запусти /api/plan."
            )

        try:
            output = indesign_bridge.run_layout_script(
                indd_path=Path(req.indd_path),
                plan_path=plan_path,
                script_path=script_path,
                issue_date=req.issue_date,
                issue_number=req.issue_number,
            )
        except indesign_bridge.IndesignBridgeError as exc:
            raise HTTPException(502, str(exc)) from exc

        return {"output": output}

    return app


app = create_app()
