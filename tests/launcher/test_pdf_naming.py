"""Tests for inkforge.launcher.pdf_naming (export_results naming convention:
{newspaper_type}_{week_number}({total_publishes})_{export_numeration}.pdf)."""

from __future__ import annotations

from pathlib import Path

from inkforge.launcher.pdf_naming import build_export_base_name, next_export_pdf_path


def test_build_export_base_name() -> None:
    assert build_export_base_name("MIF", "10", "125") == "MIF_10(125)"


def test_next_export_pdf_path_starts_at_one(tmp_path: Path) -> None:
    path = next_export_pdf_path(tmp_path, "MIF", "10", "125")

    assert path == tmp_path / "export_results" / "MIF_10(125)_1.pdf"
    assert path.parent.is_dir()


def test_next_export_pdf_path_increments_past_existing(tmp_path: Path) -> None:
    export_dir = tmp_path / "export_results"
    export_dir.mkdir()
    (export_dir / "MIF_10(125)_1.pdf").write_bytes(b"fake")
    (export_dir / "MIF_10(125)_2.pdf").write_bytes(b"fake")

    path = next_export_pdf_path(tmp_path, "MIF", "10", "125")

    assert path == export_dir / "MIF_10(125)_3.pdf"


def test_next_export_pdf_path_ignores_other_issues(tmp_path: Path) -> None:
    export_dir = tmp_path / "export_results"
    export_dir.mkdir()
    (export_dir / "MIF_9(124)_1.pdf").write_bytes(b"fake")

    path = next_export_pdf_path(tmp_path, "MIF", "10", "125")

    assert path == export_dir / "MIF_10(125)_1.pdf"
