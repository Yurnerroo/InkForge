from pathlib import Path

from inkforge.content_checker.cli import main


def test_cli_writes_manifest_and_returns_zero(tmp_path: Path, capsys) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_article.txt").write_text("Текст статті.", encoding="utf-8")

    exit_code = main([str(tmp_path), "--newspaper", "Тест"])

    assert exit_code == 0
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.is_file()
    captured = capsys.readouterr()
    assert "Тест" in captured.out


def test_cli_no_manifest_flag_skips_writing(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")

    exit_code = main([str(tmp_path), "--no-manifest"])

    assert exit_code == 0
    assert not (tmp_path / "manifest.json").is_file()


def test_cli_custom_manifest_out(tmp_path: Path) -> None:
    page_dir = tmp_path / "01"
    page_dir.mkdir()
    (page_dir / "1_1_article.txt").write_text("Текст.", encoding="utf-8")
    custom_path = tmp_path / "out" / "custom.json"

    exit_code = main([str(tmp_path), "--manifest-out", str(custom_path)])

    assert exit_code == 0
    assert custom_path.is_file()


def test_cli_returns_error_code_for_missing_folder(tmp_path: Path) -> None:
    missing = tmp_path / "nope"

    exit_code = main([str(missing)])

    assert exit_code == 2
