from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from inkforge.content_checker.docreader import read_text_metrics


def test_read_txt_counts_words(tmp_path: Path) -> None:
    path = tmp_path / "article.txt"
    path.write_text("Одне два три чотири.", encoding="utf-8")

    metrics = read_text_metrics(path)

    assert metrics.word_count == 4
    assert metrics.warnings == []


def test_read_txt_detects_short_first_paragraph_as_lead(tmp_path: Path) -> None:
    path = tmp_path / "article.txt"
    path.write_text("Короткий лід.\nДовший основний текст статті з деталями.", encoding="utf-8")

    metrics = read_text_metrics(path)

    assert metrics.has_lead_paragraph is True


def test_read_docx_counts_words_and_detects_lead_style(tmp_path: Path) -> None:
    document = Document()
    document.styles.add_style("Vrizka", WD_STYLE_TYPE.PARAGRAPH)
    lead = document.add_paragraph("Короткий лід-абзац на початку.")
    lead.style = document.styles["Vrizka"]
    document.add_paragraph("Основний текст статті з кількома словами тут.")
    path = tmp_path / "article.docx"
    document.save(str(path))

    metrics = read_text_metrics(path)

    assert metrics.word_count > 0
    assert metrics.has_lead_paragraph is True
    assert metrics.warnings == []


def test_read_docx_without_lead_style(tmp_path: Path) -> None:
    document = Document()
    document.add_paragraph("Звичайний перший абзац без спеціального стилю.")
    path = tmp_path / "article.docx"
    document.save(str(path))

    metrics = read_text_metrics(path)

    assert metrics.has_lead_paragraph is False


def test_read_text_metrics_missing_file(tmp_path: Path) -> None:
    metrics = read_text_metrics(tmp_path / "missing.txt")

    assert metrics.word_count == 0
    assert any("not found" in w for w in metrics.warnings)


def test_read_text_metrics_unsupported_legacy_doc(tmp_path: Path) -> None:
    path = tmp_path / "article.doc"
    path.write_text("legacy", encoding="utf-8")

    metrics = read_text_metrics(path)

    assert any("not supported" in w for w in metrics.warnings)


def test_read_text_metrics_unknown_extension(tmp_path: Path) -> None:
    path = tmp_path / "article.rtf"
    path.write_text("data", encoding="utf-8")

    metrics = read_text_metrics(path)

    assert any("Unsupported text format" in w for w in metrics.warnings)
