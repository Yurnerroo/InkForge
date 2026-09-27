"""FastAPI-застосунок Рівня 3 — One-Click Launcher.

Одна локальна сторінка з кнопками "Перевірити контент" / "Побудувати план
верстки" / "Зверстати в InDesign" / "Експорт друк-PDF", кожна — окремий
підтверджуваний крок (без автоланцюжка; ручне доправлення в самому InDesign
лишається між кроками "Зверстати" і "Експорт" — не автоматизується).
/api/check і /api/plan — тонкі обгортки над вже протестованим кодом
Рівня 1/2. /api/execute і /api/export_pdf делегують в `indesign_bridge`
(COM, лише Windows, не перевірено на реальному InDesign). Див.
docs/architecture.md, "Рівень 3".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..content_checker.manifest import build_manifest, write_manifest
from ..content_checker.scanner import FONTS_FOLDER_NAME, is_fonts_folder_name, scan_issue
from ..content_checker.structure_validator import validate_issue_structure
from ..layout_engine.planner import build_layout_plan
from ..layout_engine.planwriter import write_layout_plan
from ..layout_engine.profile import ProfileError, resolve_profile
from . import indesign_bridge
from .font_provisioner import provision_missing_fonts
from .pdf_naming import next_export_pdf_path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILES_DIR = REPO_ROOT / "profiles"
DEFAULT_SCRIPT_PATH = REPO_ROOT / "extendscript" / "inkforge_layout.jsx"
DEFAULT_PDF_SCRIPT_PATH = REPO_ROOT / "extendscript" / "inkforge_export_pdf.jsx"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class IssueRequest(BaseModel):
    issue_folder: str
    profile: str


class ValidateStructureRequest(BaseModel):
    issue_folder: str
    # Необов'язковий -- якщо профіль ще не обрано або невідомий, перевірка
    # просто не зможе звільнити від вимоги контенту "ручні" сторінки
    # профілю, решта перевірок (FONTS, сторінкові підпапки) не залежать
    # від профілю взагалі.
    profile: str | None = None


class ExecuteRequest(IssueRequest):
    indd_path: str
    issue_date: str | None = None
    issue_number: str | None = None


class ExportPdfRequest(IssueRequest):
    # Необов'язковий -- якщо не задано, шлях обчислюється автоматично за
    # конвенцією найменування у виділеній підпапці issue_folder/export_results
    # (див. pdf_naming.py); вимагає issue_number і total_publishes.
    pdf_path: str | None = None
    # Fallback, лише якщо в InDesign немає вже відкритого документа (див.
    # inkforge_export_pdf.jsx, getTargetDocument). Типово доправлений
    # документ уже відкритий після кроків 3-4, тому не обов'язково.
    indd_path: str | None = None
    preset_name: str | None = None
    # Для авто-імені PDF за конвенцією "{тип}_{номер}({наскрізний})_{n}.pdf":
    issue_number: str | None = None
    total_publishes: str | None = None


def list_profile_ids(profiles_dir: Path) -> list[str]:
    if not profiles_dir.is_dir():
        return []
    return sorted(path.stem for path in profiles_dir.glob("*.yaml"))


def _find_fonts_folder(issue_path: Path) -> Path | None:
    """Знаходить обов'язкову підпапку шрифтів усередині ``issue_path``
    (регістронезалежно), або ``None``, якщо її немає."""

    if not issue_path.is_dir():
        return None
    for child in issue_path.iterdir():
        if child.is_dir() and is_fonts_folder_name(child.name):
            return child
    return None


def _show_folder_dialog(title: str) -> str | None:
    """Показує нативний діалог вибору папки (блокуючий) і повертає обраний
    шлях, або ``None``, якщо користувач скасував. Браузер не може віддати
    реальний абсолютний шлях файлової системи (лише fake-шлях з
    <input type="file">), тому вибір робить сам Python-бекенд через
    tkinter.filedialog — окрема функція, щоб тести могли підмінити її без
    реального GUI."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askdirectory(title=title)
    finally:
        root.destroy()
    return path or None


def _show_open_file_dialog(title: str, filetypes: list[tuple[str, str]]) -> str | None:
    """Те саме, що ``_show_folder_dialog``, але для вибору наявного файлу."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    finally:
        root.destroy()
    return path or None


def _show_save_file_dialog(
    title: str, default_ext: str, filetypes: list[tuple[str, str]]
) -> str | None:
    """Те саме, але для вибору шляху збереження (файл може ще не існувати)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.asksaveasfilename(
            title=title, defaultextension=default_ext, filetypes=filetypes
        )
    finally:
        root.destroy()
    return path or None


def create_app(
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    script_path: Path = DEFAULT_SCRIPT_PATH,
    pdf_script_path: Path = DEFAULT_PDF_SCRIPT_PATH,
) -> FastAPI:
    """Build the launcher's FastAPI app.

    ``profiles_dir``/``script_path``/``pdf_script_path`` are overridable so
    tests can point at fixture directories instead of the real repo-level
    ``profiles/``, ``extendscript/inkforge_layout.jsx`` and
    ``extendscript/inkforge_export_pdf.jsx``.
    """

    app = FastAPI(title="InkForge Launcher")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/api/profiles")
    def profiles() -> dict[str, Any]:
        return {"profiles": list_profile_ids(profiles_dir)}

    @app.get("/api/pick_folder")
    def pick_folder() -> dict[str, Any]:
        return {"path": _show_folder_dialog("Виберіть папку тижневого випуску")}

    @app.get("/api/pick_indd")
    def pick_indd() -> dict[str, Any]:
        path = _show_open_file_dialog(
            "Виберіть файл-основу .indd",
            [("InDesign", "*.indd"), ("Усі файли", "*.*")],
        )
        return {"path": path}

    @app.get("/api/pick_pdf_save")
    def pick_pdf_save() -> dict[str, Any]:
        path = _show_save_file_dialog(
            "Куди зберегти друк-PDF",
            ".pdf",
            [("PDF", "*.pdf"), ("Усі файли", "*.*")],
        )
        return {"path": path}

    @app.post("/api/validate_structure")
    def validate_structure(req: ValidateStructureRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        profile = None
        if req.profile:
            try:
                profile = resolve_profile(req.profile, profiles_dir)
            except ProfileError:
                profile = None  # профіль ще не обрано/невідомий -- не блокуємо перевірку структури через це

        result = validate_issue_structure(issue_path, profile)
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "pages_found": result.pages_found,
            "fonts_folder": result.fonts_folder,
        }

    @app.post("/api/check")
    def check(req: IssueRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        if not issue_path.is_dir():
            raise HTTPException(400, f"Папку випуску не знайдено: {issue_path}")

        try:
            profile = resolve_profile(req.profile, profiles_dir)
        except ProfileError:
            profile = None  # див. коментар у validate_structure() вище

        structure = validate_issue_structure(issue_path, profile)
        if not structure.valid:
            raise HTTPException(400, "; ".join(structure.errors))

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

        fonts_dir = _find_fonts_folder(issue_path)
        if fonts_dir is None:
            raise HTTPException(
                400,
                "Не знайдено папку зі шрифтами. Створіть підпапку "
                f"'{FONTS_FOLDER_NAME}' безпосередньо всередині папки випуску "
                f"(тобто {issue_path / FONTS_FOLDER_NAME}) і покладіть туди "
                "файли шрифтів (.ttf/.otf/.ttc), потрібні для цього випуску.",
            )

        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        font_names = list(plan_data.get("fonts_installed") or []) + list(
            plan_data.get("fonts_substituted") or []
        )
        fonts_provisioned = provision_missing_fonts(
            font_names, fonts_dir, Path(req.indd_path)
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

        return {"output": output, "fonts_provisioned": fonts_provisioned}

    @app.post("/api/export_pdf")
    def export_pdf(req: ExportPdfRequest) -> dict[str, Any]:
        issue_path = Path(req.issue_folder)
        plan_path = issue_path / "layout_plan.json"
        if not plan_path.is_file():
            raise HTTPException(
                400, "layout_plan.json не знайдено — спочатку запусти /api/plan."
            )

        if req.pdf_path:
            pdf_path = Path(req.pdf_path)
        else:
            if not req.issue_number or not req.total_publishes:
                raise HTTPException(
                    400,
                    "Для автоматичного імені PDF потрібні issue_number "
                    "(номер випуску) і total_publishes (наскрізний номер) — "
                    "або вкажи pdf_path вручну.",
                )
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            newspaper_type = str(plan_data.get("newspaper_id") or req.profile).upper()
            pdf_path = next_export_pdf_path(
                issue_path, newspaper_type, req.issue_number, req.total_publishes
            )

        try:
            output = indesign_bridge.run_export_pdf_script(
                plan_path=plan_path,
                pdf_path=pdf_path,
                script_path=pdf_script_path,
                indd_path=Path(req.indd_path) if req.indd_path else None,
                preset_name=req.preset_name,
            )
        except indesign_bridge.IndesignBridgeError as exc:
            raise HTTPException(502, str(exc)) from exc

        return {"output": output, "pdf_path": str(pdf_path)}

    return app


app = create_app()
