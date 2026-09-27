"""Tests for inkforge.launcher.app (Рівень 3 — One-Click Launcher API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inkforge.launcher import app as app_module
from inkforge.launcher.app import create_app

PROFILE_YAML = """
id: test_gazeta
display_name: "Test Gazeta"
page_count: 3
manual_pages: []
manual_pages_uncertain: []
spreads:
  - pages: [1]
    color_mode: grayscale
color_alternation_pattern: "n/a"
cmyk_profile: null
photo_links:
  storage: linked
  naming_pattern: "Links/{page}.{ext}"
paragraph_styles_found: [Body]
paragraph_style_roles:
  body: [Body]
special_pages: []
fonts_installed: [Arial]
fonts_substituted: []
frame_stability: partial
samples_analyzed: [issue01]
notes: ""
"""


def _make_issue(tmp_path: Path) -> Path:
    issue_dir = tmp_path / "2026-W40_test-gazeta"
    page_dir = issue_dir / "01"
    page_dir.mkdir(parents=True)
    (page_dir / "1_1_article.txt").write_text("Текст статті для перевірки.", encoding="utf-8")
    fonts_dir = issue_dir / "FONTS"
    fonts_dir.mkdir()
    (fonts_dir / "Arial.ttf").write_bytes(b"fake-ttf")
    return issue_dir


def _make_client(tmp_path: Path) -> TestClient:
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "test_gazeta.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    app = create_app(
        profiles_dir=profiles_dir,
        script_path=tmp_path / "no_such_script.jsx",
        pdf_script_path=tmp_path / "no_such_pdf_script.jsx",
    )
    return TestClient(app)


def test_index_serves_html(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "InkForge" in response.text


def test_list_profiles(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    response = client.get("/api/profiles")

    assert response.status_code == 200
    assert response.json() == {"profiles": ["test_gazeta"]}


def test_check_then_plan_flow(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)

    check_resp = client.post(
        "/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"}
    )
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert (issue_dir / "manifest.json").is_file()
    assert len(check_data["pages"]) == 1
    assert check_data["pages"][0]["articles"] == 1

    plan_resp = client.post(
        "/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"}
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert (issue_dir / "layout_plan.json").is_file()
    assert any(page["page"] == 1 for page in plan_data["pages"])


def test_plan_without_check_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)

    response = client.post(
        "/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"}
    )

    assert response.status_code == 400
    assert "manifest.json" in response.json()["detail"]


def test_check_missing_folder_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    response = client.post(
        "/api/check",
        json={"issue_folder": str(tmp_path / "nope"), "profile": "test_gazeta"},
    )

    assert response.status_code == 400


def test_execute_without_plan_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)

    response = client.post(
        "/api/execute",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "indd_path": str(issue_dir / "does_not_exist.indd"),
        },
    )

    assert response.status_code == 400
    assert "layout_plan.json" in response.json()["detail"]


def test_execute_after_plan_fails_gracefully_without_indesign(tmp_path: Path) -> None:
    """No InDesign/pywin32 is available in this dev environment -- /api/execute
    must fail with a clear 502, not crash the server. This is a real,
    honest assertion about the current environment, not a mock."""

    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})

    response = client.post(
        "/api/execute",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "indd_path": str(issue_dir / "does_not_exist.indd"),
        },
    )

    assert response.status_code == 502


def test_export_pdf_without_plan_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)

    response = client.post(
        "/api/export_pdf",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "pdf_path": str(issue_dir / "out.pdf"),
        },
    )

    assert response.status_code == 400
    assert "layout_plan.json" in response.json()["detail"]


def test_pick_folder_returns_dialog_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No real GUI is available in tests, so the tkinter dialog call is
    monkeypatched -- the endpoint itself just has to plumb the result through."""

    client = _make_client(tmp_path)
    monkeypatch.setattr(app_module, "_show_folder_dialog", lambda title: r"C:\chosen\folder")

    response = client.get("/api/pick_folder")

    assert response.status_code == 200
    assert response.json() == {"path": r"C:\chosen\folder"}


def test_pick_folder_returns_none_when_cancelled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(tmp_path)
    monkeypatch.setattr(app_module, "_show_folder_dialog", lambda title: None)

    response = client.get("/api/pick_folder")

    assert response.status_code == 200
    assert response.json() == {"path": None}


def test_pick_indd_returns_dialog_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(tmp_path)
    monkeypatch.setattr(
        app_module, "_show_open_file_dialog", lambda title, filetypes: r"C:\chosen\gazeta.indd"
    )

    response = client.get("/api/pick_indd")

    assert response.status_code == 200
    assert response.json() == {"path": r"C:\chosen\gazeta.indd"}


def test_pick_pdf_save_returns_dialog_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(tmp_path)
    monkeypatch.setattr(
        app_module,
        "_show_save_file_dialog",
        lambda title, default_ext, filetypes: r"C:\chosen\out.pdf",
    )

    response = client.get("/api/pick_pdf_save")

    assert response.status_code == 200
    assert response.json() == {"path": r"C:\chosen\out.pdf"}


def test_execute_with_fonts_folder_provisions_fonts_before_failing(tmp_path: Path) -> None:
    """No real InDesign is available in tests (still a 502, same as
    test_execute_after_plan_fails_gracefully_without_indesign), but font
    provisioning runs before the InDesign call and must still leave the
    matching font file copied into "Document Fonts" next to the .indd. The
    FONTS folder itself is the required `issue_dir/FONTS` subfolder from
    _make_issue -- no separate fonts_folder argument exists anymore."""

    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})

    indd_path = issue_dir / "gazeta.indd"
    indd_path.write_bytes(b"fake-indd")

    response = client.post(
        "/api/execute",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "indd_path": str(indd_path),
        },
    )

    assert response.status_code == 502
    copied_file = issue_dir / "Document Fonts" / "Arial.ttf"
    assert copied_file.is_file()


def test_execute_without_fonts_folder_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    import shutil

    shutil.rmtree(issue_dir / "FONTS")
    indd_path = issue_dir / "gazeta.indd"
    indd_path.write_bytes(b"fake-indd")

    response = client.post(
        "/api/execute",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "indd_path": str(indd_path),
        },
    )

    assert response.status_code == 400
    assert "FONTS" in response.json()["detail"]


def test_export_pdf_after_plan_fails_gracefully_without_indesign(tmp_path: Path) -> None:
    """Same honest assertion as test_execute_after_plan_fails_gracefully_without_indesign,
    but for /api/export_pdf (Рівень 3, крок 5)."""

    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})

    response = client.post(
        "/api/export_pdf",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "pdf_path": str(issue_dir / "out.pdf"),
        },
    )

    assert response.status_code == 502


def test_export_pdf_auto_names_when_pdf_path_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})

    monkeypatch.setattr(
        app_module.indesign_bridge, "run_export_pdf_script", lambda **kwargs: "ok"
    )

    response = client.post(
        "/api/export_pdf",
        json={
            "issue_folder": str(issue_dir),
            "profile": "test_gazeta",
            "issue_number": "10",
            "total_publishes": "125",
        },
    )

    assert response.status_code == 200
    data = response.json()
    expected = issue_dir / "export_results" / "TEST_GAZETA_10(125)_1.pdf"
    assert Path(data["pdf_path"]) == expected
    assert expected.parent.is_dir()


def test_export_pdf_without_path_or_numbers_returns_400(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    client.post("/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})
    client.post("/api/plan", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"})

    response = client.post(
        "/api/export_pdf",
        json={"issue_folder": str(issue_dir), "profile": "test_gazeta"},
    )

    assert response.status_code == 400


def test_validate_structure_valid_issue(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)

    response = client.post(
        "/api/validate_structure",
        json={"issue_folder": str(issue_dir), "profile": "test_gazeta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["pages_found"] == ["01"]
    assert data["errors"] == []


def test_validate_structure_missing_fonts_folder(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    import shutil

    shutil.rmtree(issue_dir / "FONTS")

    response = client.post(
        "/api/validate_structure",
        json={"issue_folder": str(issue_dir), "profile": "test_gazeta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any("FONTS" in e for e in data["errors"])


def test_check_blocks_when_fonts_folder_missing(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    issue_dir = _make_issue(tmp_path)
    import shutil

    shutil.rmtree(issue_dir / "FONTS")

    response = client.post(
        "/api/check", json={"issue_folder": str(issue_dir), "profile": "test_gazeta"}
    )

    assert response.status_code == 400
    assert "FONTS" in response.json()["detail"]
