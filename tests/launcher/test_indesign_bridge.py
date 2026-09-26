"""Tests for inkforge.launcher.indesign_bridge.

No real InDesign/pywin32 is available in this dev environment, so these
tests exercise the fail-safe guards (missing Windows/pywin32/files) with a
faked ``win32com.client`` module rather than asserting anything about real
COM automation -- see docs/architecture.md, "Відкриті питання".
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from inkforge.launcher import indesign_bridge


def test_non_windows_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(indesign_bridge.IndesignBridgeError, match="Windows"):
        indesign_bridge.run_layout_script(Path("a.indd"), Path("plan.json"), Path("script.jsx"))


def test_missing_pywin32_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "win32com", None)
    monkeypatch.setitem(sys.modules, "win32com.client", None)

    with pytest.raises(indesign_bridge.IndesignBridgeError, match="pywin32"):
        indesign_bridge.run_layout_script(Path("a.indd"), Path("plan.json"), Path("script.jsx"))


def _install_fake_win32com(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    fake_client = types.SimpleNamespace()
    fake_win32com = types.SimpleNamespace(client=fake_client)
    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)
    monkeypatch.setattr(sys, "platform", "win32")
    return fake_client


def test_missing_indd_file_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_win32com(monkeypatch)
    plan_path = tmp_path / "layout_plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    script_path = tmp_path / "script.jsx"
    script_path.write_text("", encoding="utf-8")

    with pytest.raises(indesign_bridge.IndesignBridgeError, match="indd"):
        indesign_bridge.run_layout_script(tmp_path / "missing.indd", plan_path, script_path)


def test_missing_plan_file_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_win32com(monkeypatch)
    indd_path = tmp_path / "issue.indd"
    indd_path.write_text("", encoding="utf-8")
    script_path = tmp_path / "script.jsx"
    script_path.write_text("", encoding="utf-8")

    with pytest.raises(indesign_bridge.IndesignBridgeError, match="layout_plan.json"):
        indesign_bridge.run_layout_script(indd_path, tmp_path / "missing_plan.json", script_path)


def test_successful_run_sets_script_args_and_calls_doscript(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_client = _install_fake_win32com(monkeypatch)

    indd_path = tmp_path / "issue.indd"
    indd_path.write_text("", encoding="utf-8")
    plan_path = tmp_path / "layout_plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    script_path = tmp_path / "script.jsx"
    script_path.write_text("", encoding="utf-8")

    set_values: dict[str, str] = {}

    class FakeScriptArgs:
        def SetValue(self, key: str, value: str) -> None:  # noqa: N802 - COM naming
            set_values[key] = value

    class FakeApp:
        ScriptArgs = FakeScriptArgs()

        def DoScript(self, script: str, language: object) -> str:  # noqa: N802
            assert script == str(script_path)
            return "OK"

    fake_client.gencache = types.SimpleNamespace(EnsureDispatch=lambda _name: FakeApp())
    fake_client.constants = types.SimpleNamespace(idJavascript="javascript")

    result = indesign_bridge.run_layout_script(
        indd_path,
        plan_path,
        script_path,
        issue_date="2026-10-01",
        issue_number="40",
    )

    assert result == "OK"
    assert set_values == {
        "docPath": str(indd_path),
        "planPath": str(plan_path),
        "issueDate": "2026-10-01",
        "issueNumber": "40",
    }
