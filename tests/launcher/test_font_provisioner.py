"""Tests for inkforge.launcher.font_provisioner."""

from __future__ import annotations

from pathlib import Path

from inkforge.launcher.font_provisioner import (
    index_font_files,
    provision_missing_fonts,
)


def test_index_font_files_matches_by_normalized_name(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "FONTS"
    fonts_dir.mkdir()
    (fonts_dir / "UKRAINIANXENIAEXTENDED.ttf").write_bytes(b"fake-ttf")
    (fonts_dir / "Everest-Demi.otf").write_bytes(b"fake-otf")
    (fonts_dir / "notes.txt").write_text("not a font", encoding="utf-8")

    index = index_font_files(fonts_dir)

    assert set(index.keys()) == {"ukrainianxeniaextended", "everestdemi"}


def test_index_font_files_returns_empty_for_missing_folder(tmp_path: Path) -> None:
    assert index_font_files(tmp_path / "does_not_exist") == {}


def test_provision_missing_fonts_copies_matching_files(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "FONTS"
    fonts_dir.mkdir()
    (fonts_dir / "UKRAINIANXENIAEXTENDED.ttf").write_bytes(b"fake-ttf")

    issue_dir = tmp_path / "issue"
    issue_dir.mkdir()
    indd_path = issue_dir / "gazeta.indd"
    indd_path.write_bytes(b"fake-indd")

    result = provision_missing_fonts(
        ["Arial", "UkrainianXeniaExtended"], fonts_dir, indd_path
    )

    assert result == {"copied": ["UkrainianXeniaExtended"], "not_found": ["Arial"]}
    copied_file = issue_dir / "Document Fonts" / "UKRAINIANXENIAEXTENDED.ttf"
    assert copied_file.is_file()
    assert copied_file.read_bytes() == b"fake-ttf"


def test_provision_missing_fonts_with_no_fonts_folder(tmp_path: Path) -> None:
    indd_path = tmp_path / "issue" / "gazeta.indd"
    indd_path.parent.mkdir()

    result = provision_missing_fonts(["Arial"], tmp_path / "no_such_folder", indd_path)

    assert result == {"copied": [], "not_found": ["Arial"]}
    assert not (indd_path.parent / "Document Fonts").exists()


def test_provision_missing_fonts_does_not_recopy_unchanged_file(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "FONTS"
    fonts_dir.mkdir()
    src = fonts_dir / "Arial.ttf"
    src.write_bytes(b"fake-ttf")

    issue_dir = tmp_path / "issue"
    issue_dir.mkdir()
    indd_path = issue_dir / "gazeta.indd"
    indd_path.write_bytes(b"fake-indd")

    provision_missing_fonts(["Arial"], fonts_dir, indd_path)
    dest = issue_dir / "Document Fonts" / "Arial.ttf"
    first_mtime = dest.stat().st_mtime

    provision_missing_fonts(["Arial"], fonts_dir, indd_path)

    assert dest.stat().st_mtime == first_mtime
