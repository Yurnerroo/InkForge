"""Tests for inkforge.content_checker.structure_validator (fast, blocking
structural validation right after picking the issue folder in the launcher)."""

from __future__ import annotations

from pathlib import Path

from inkforge.content_checker.structure_validator import validate_issue_structure
from inkforge.layout_engine.profile import load_profile

PROFILE_YAML = """
id: test_gazeta
display_name: "Test Gazeta"
page_count: 2
manual_pages: [2]
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


def _make_valid_issue(root: Path) -> None:
    page_dir = root / "01"
    page_dir.mkdir(parents=True)
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")
    fonts_dir = root / "FONTS"
    fonts_dir.mkdir()
    (fonts_dir / "Arial.ttf").write_bytes(b"fake-ttf")


def test_valid_issue_passes(tmp_path: Path) -> None:
    _make_valid_issue(tmp_path)

    result = validate_issue_structure(tmp_path)

    assert result.valid is True
    assert result.errors == []
    assert result.pages_found == ["01"]
    assert result.fonts_folder is not None


def test_missing_root_folder_is_blocking(tmp_path: Path) -> None:
    result = validate_issue_structure(tmp_path / "nope")

    assert result.valid is False
    assert "не знайдено" in result.errors[0].lower()


def test_missing_fonts_folder_is_blocking(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir(parents=True)
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")

    result = validate_issue_structure(tmp_path)

    assert result.valid is False
    assert any("FONTS" in e for e in result.errors)


def test_fonts_folder_name_is_case_insensitive(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir(parents=True)
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    (fonts_dir / "Arial.ttf").write_bytes(b"fake-ttf")

    result = validate_issue_structure(tmp_path)

    assert result.valid is True


def test_empty_fonts_folder_is_a_warning_not_blocking(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir(parents=True)
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")
    (tmp_path / "FONTS").mkdir()

    result = validate_issue_structure(tmp_path)

    assert result.valid is True
    assert any("не містить жодного файлу шрифту" in w for w in result.warnings)


def test_no_page_folders_is_blocking(tmp_path: Path) -> None:
    (tmp_path / "FONTS").mkdir(parents=True)
    ((tmp_path / "FONTS") / "Arial.ttf").write_bytes(b"fake-ttf")

    result = validate_issue_structure(tmp_path)

    assert result.valid is False
    assert any("сторінкової підпапки" in e for e in result.errors)


def test_empty_page_folder_is_blocking(tmp_path: Path) -> None:
    _make_valid_issue(tmp_path)
    (tmp_path / "02").mkdir()

    result = validate_issue_structure(tmp_path)

    assert result.valid is False
    assert any("02" in e and "порожня" in e for e in result.errors)


def test_empty_page_folder_exempted_when_manual_in_profile(tmp_path: Path, tmp_path_factory) -> None:
    _make_valid_issue(tmp_path)
    (tmp_path / "02").mkdir()
    profile_path = tmp_path_factory.mktemp("profiles") / "test_gazeta.yaml"
    profile_path.write_text(PROFILE_YAML, encoding="utf-8")
    profile = load_profile(profile_path)

    result = validate_issue_structure(tmp_path, profile)

    assert result.valid is True


def test_unrecognized_subfolder_is_a_warning_not_blocking(tmp_path: Path) -> None:
    _make_valid_issue(tmp_path)
    (tmp_path / "notes").mkdir()

    result = validate_issue_structure(tmp_path)

    assert result.valid is True
    assert any("Непізнана підпапка" in w for w in result.warnings)
