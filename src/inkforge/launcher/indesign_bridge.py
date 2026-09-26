"""COM-міст, що керує Adobe InDesign для запуску ExtendScript-скриптів
Рівня 2/3: ``run_layout_script`` — верстка (``inkforge_layout.jsx``, крок 3),
``run_export_pdf_script`` — друк-PDF (``inkforge_export_pdf.jsx``, крок 5).

**НЕ перевірено на реальному InDesign** (у поточному dev-оточенні InDesign
не встановлено) — див. `docs/architecture.md`, "Відкриті питання". Замість
здогадок цей модуль явно перевіряє наявність `pywin32` і живого InDesign й
кидає зрозумілу помилку, якщо їх немає — той самий принцип "не вгадувати",
що й у `extendscript/inkforge_layout.jsx`.

Ключова ідея: цей модуль сам НЕ відкриває ``.indd`` файл через COM — він лише
проставляє ``app.scriptArgs`` (``docPath``, ``planPath``, за наявності
``issueDate``/``issueNumber``/``pdfPath``/``presetName``) і запускає
відповідний .jsx, а той вже сам читає ці аргументи й відкриває/використовує
документ (``pickFile``/``getTargetDocument``/``main()`` у jsx це вже
підтримують). Так уникаємо подвійного відкриття файлу.
"""

from __future__ import annotations

import sys
from pathlib import Path


class IndesignBridgeError(RuntimeError):
    """Кидається, коли керування InDesign неможливе (немає pywin32/Windows/
    файлів) або сам InDesign повернув помилку виконання скрипту."""


def _win32com_client():
    if sys.platform != "win32":
        raise IndesignBridgeError(
            "Керування InDesign через COM доступне лише на Windows."
        )
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise IndesignBridgeError(
            "Пакет pywin32 не встановлено. Встанови: pip install 'inkforge[launcher]'"
        ) from exc
    return win32com.client


def run_layout_script(
    indd_path: Path,
    plan_path: Path,
    script_path: Path,
    issue_date: str | None = None,
    issue_number: str | None = None,
) -> str:
    """Запускає ``script_path`` (inkforge_layout.jsx) всередині InDesign.

    Повертає те, що напише скрипт через ``$.writeln`` (для діагностики), або
    кидає ``IndesignBridgeError``. **Ця функція не виконувалась проти
    реального InDesign** — сигнатура й назви COM-методів відповідають
    документованому Adobe InDesign Scripting DOM, але потребують підтвердження
    на реальній машині верстальниці.
    """

    win32com = _win32com_client()

    indd_path = Path(indd_path)
    plan_path = Path(plan_path)
    script_path = Path(script_path)

    if not indd_path.is_file():
        raise IndesignBridgeError(f".indd файл не знайдено: {indd_path}")
    if not plan_path.is_file():
        raise IndesignBridgeError(f"layout_plan.json не знайдено: {plan_path}")
    if not script_path.is_file():
        raise IndesignBridgeError(f"ExtendScript-файл не знайдено: {script_path}")

    try:
        app = win32com.gencache.EnsureDispatch("InDesign.Application")
    except Exception as exc:  # pragma: no cover - потребує реального InDesign
        raise IndesignBridgeError(f"Не вдалося підключитися до InDesign: {exc}") from exc

    script_args: dict[str, str] = {
        "docPath": str(indd_path),
        "planPath": str(plan_path),
    }
    if issue_date:
        script_args["issueDate"] = issue_date
    if issue_number:
        script_args["issueNumber"] = issue_number

    try:
        for key, value in script_args.items():
            app.ScriptArgs.SetValue(key, value)
        result = app.DoScript(str(script_path), win32com.constants.idJavascript)
    except Exception as exc:  # pragma: no cover - потребує реального InDesign
        raise IndesignBridgeError(f"Помилка виконання скрипту в InDesign: {exc}") from exc

    return str(result) if result is not None else ""


def run_export_pdf_script(
    plan_path: Path,
    pdf_path: Path,
    script_path: Path,
    indd_path: Path | None = None,
    preset_name: str | None = None,
) -> str:
    """Запускає ``script_path`` (inkforge_export_pdf.jsx) — Рівень 3, крок 5.

    На відміну від ``run_layout_script``, НЕ вимагає ``indd_path``: якщо в
    InDesign вже є відкритий документ (типовий випадок одразу після кроку 3
    і ручного доправлення), скрипт сам використає саме його. ``indd_path``
    лишається лише fallback-ом на випадок окремо запущеного InDesign без
    відкритого документа.

    **Ця функція не виконувалась проти реального InDesign** — див.
    застереження в ``run_layout_script`` і ``extendscript/inkforge_export_pdf.jsx``.
    """

    win32com = _win32com_client()

    plan_path = Path(plan_path)
    pdf_path = Path(pdf_path)
    script_path = Path(script_path)

    if not plan_path.is_file():
        raise IndesignBridgeError(f"layout_plan.json не знайдено: {plan_path}")
    if not script_path.is_file():
        raise IndesignBridgeError(f"ExtendScript-файл не знайдено: {script_path}")
    if indd_path is not None and not Path(indd_path).is_file():
        raise IndesignBridgeError(f".indd файл не знайдено: {indd_path}")

    try:
        app = win32com.gencache.EnsureDispatch("InDesign.Application")
    except Exception as exc:  # pragma: no cover - потребує реального InDesign
        raise IndesignBridgeError(f"Не вдалося підключитися до InDesign: {exc}") from exc

    script_args: dict[str, str] = {
        "planPath": str(plan_path),
        "pdfPath": str(pdf_path),
    }
    if indd_path is not None:
        script_args["docPath"] = str(indd_path)
    if preset_name:
        script_args["presetName"] = preset_name

    try:
        for key, value in script_args.items():
            app.ScriptArgs.SetValue(key, value)
        result = app.DoScript(str(script_path), win32com.constants.idJavascript)
    except Exception as exc:  # pragma: no cover - потребує реального InDesign
        raise IndesignBridgeError(f"Помилка виконання скрипту в InDesign: {exc}") from exc

    return str(result) if result is not None else ""
