"""COM-міст, що керує Adobe InDesign для запуску ``inkforge_layout.jsx``.

**НЕ перевірено на реальному InDesign** (у поточному dev-оточенні InDesign
не встановлено) — див. `docs/architecture.md`, "Відкриті питання". Замість
здогадок цей модуль явно перевіряє наявність `pywin32` і живого InDesign й
кидає зрозумілу помилку, якщо їх немає — той самий принцип "не вгадувати",
що й у `extendscript/inkforge_layout.jsx`.

Ключова ідея: цей модуль сам НЕ відкриває ``.indd`` файл через COM — він лише
проставляє ``app.scriptArgs`` (``docPath``, ``planPath``, за наявності
``issueDate``/``issueNumber``) і запускає ``inkforge_layout.jsx``, а той вже
сам читає ці аргументи й відкриває документ (``pickFile``/``main()`` у jsx це
вже підтримують). Так уникаємо подвійного відкриття файлу.
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
