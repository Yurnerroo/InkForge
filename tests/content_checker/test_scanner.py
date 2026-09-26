from pathlib import Path

from inkforge.content_checker.scanner import scan_issue


def test_scan_issue_matches_text_and_photo_by_stem(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_lider.txt").write_text("Перше слово другое.", encoding="utf-8")
    (page_dir / "1_1_lider.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    issue = scan_issue(tmp_path, newspaper="Тест")

    assert issue.newspaper == "Тест"
    assert len(issue.pages) == 1
    page = issue.pages[0]
    assert page.page == "01"
    assert len(page.articles) == 1
    article = page.articles[0]
    assert article.article_id == "01_1_lider"
    assert article.text_path is not None
    assert article.image_path is not None
    assert article.word_count == 3


def test_scan_issue_flags_photo_without_text(tmp_path: Path) -> None:
    page_dir = tmp_path / "02"
    page_dir.mkdir()
    (page_dir / "2_1_photo-only.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    issue = scan_issue(tmp_path)

    assert any("without a matching text file" in w for w in issue.all_warnings)


def test_scan_issue_flags_duplicate_order(tmp_path: Path) -> None:
    page_dir = tmp_path / "03"
    page_dir.mkdir()
    (page_dir / "3_1_first.txt").write_text("Текст.", encoding="utf-8")
    (page_dir / "3_1_second.txt").write_text("Текст.", encoding="utf-8")

    issue = scan_issue(tmp_path)

    assert any("Duplicate article order" in w for w in issue.all_warnings)


def test_scan_issue_flags_unrecognized_file_name(tmp_path: Path) -> None:
    page_dir = tmp_path / "04"
    page_dir.mkdir()
    (page_dir / "not-following-convention.txt").write_text("Текст.", encoding="utf-8")

    issue = scan_issue(tmp_path)

    assert any("doesn't match" in w for w in issue.all_warnings)


def test_scan_issue_flags_unrecognized_extension(tmp_path: Path) -> None:
    page_dir = tmp_path / "05"
    page_dir.mkdir()
    (page_dir / "5_1_article.pdf").write_bytes(b"%PDF-1.4")

    issue = scan_issue(tmp_path)

    assert any("Unrecognized file skipped" in w for w in issue.all_warnings)


def test_scan_issue_flags_page_prefix_mismatch(tmp_path: Path) -> None:
    page_dir = tmp_path / "06"
    page_dir.mkdir()
    (page_dir / "7_1_wrong-prefix.txt").write_text("Текст.", encoding="utf-8")

    issue = scan_issue(tmp_path)

    assert any("differs from folder page" in w for w in issue.all_warnings)


def test_scan_issue_reports_missing_folder(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    issue = scan_issue(missing)

    assert issue.pages == []
    assert any("not found" in w for w in issue.warnings)


def test_scan_issue_sorts_pages_and_articles_numerically(tmp_path: Path) -> None:
    for page in ("10", "02", "01"):
        page_dir = tmp_path / page
        page_dir.mkdir()
        (page_dir / f"{page}_2_second.txt").write_text("Текст.", encoding="utf-8")
        (page_dir / f"{page}_1_first.txt").write_text("Текст.", encoding="utf-8")

    issue = scan_issue(tmp_path)

    assert [p.page for p in issue.pages] == ["01", "02", "10"]
    assert [a.order for a in issue.pages[0].articles] == [1, 2]
