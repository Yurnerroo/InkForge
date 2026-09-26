import json
from pathlib import Path

from inkforge.content_checker.manifest import build_manifest, write_manifest
from inkforge.content_checker.scanner import scan_issue


def test_build_manifest_serializes_pages_and_articles(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_lider.txt").write_text("Слово раз два.", encoding="utf-8")

    issue = scan_issue(tmp_path, newspaper="Тест")
    manifest = build_manifest(issue)

    assert manifest["newspaper"] == "Тест"
    assert manifest["root"] == str(tmp_path)
    assert len(manifest["pages"]) == 1
    article = manifest["pages"][0]["articles"][0]
    assert article["article_id"] == "01_1_lider"
    assert article["word_count"] == 3
    assert article["image"] is None
    assert article["sub_order"] == 0


def test_build_manifest_includes_warnings(tmp_path: Path) -> None:
    page_dir = tmp_path / "02"
    page_dir.mkdir()
    (page_dir / "2_1_photo-only.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    issue = scan_issue(tmp_path)
    manifest = build_manifest(issue)

    assert len(manifest["warnings"]) >= 1


def test_write_manifest_produces_valid_json(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_lider.txt").write_text("Текст.", encoding="utf-8")

    issue = scan_issue(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(issue, manifest_path)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["pages"][0]["articles"][0]["char_count"] == len("Текст.")
