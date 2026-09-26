from pathlib import Path

from inkforge.content_checker.report import render_report
from inkforge.content_checker.scanner import scan_issue


def test_render_report_lists_warnings(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_photo.jpg").write_bytes(b"\x00")  # photo without text

    issue = scan_issue(tmp_path)
    report = render_report(issue)

    assert "01" in report
    assert "⚠" in report
    assert "Знайдено попереджень" in report


def test_render_report_ok_when_no_warnings(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_article.txt").write_text("Один два три.", encoding="utf-8")

    issue = scan_issue(tmp_path)
    report = render_report(issue)

    assert "готовий" in report
    assert "1 стаття" in report


def test_render_report_pluralizes_article_count() -> None:
    from inkforge.content_checker.report import _pluralize_articles

    assert _pluralize_articles(1) == "стаття"
    assert _pluralize_articles(2) == "статті"
    assert _pluralize_articles(5) == "статей"
    assert _pluralize_articles(11) == "статей"
    assert _pluralize_articles(21) == "стаття"
