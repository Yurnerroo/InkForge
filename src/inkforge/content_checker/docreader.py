"""Read text metrics from an article's source document.

Supports ``.docx`` (via python-docx) and plain ``.txt``. Legacy ``.doc``
(binary Word format) cannot be parsed without external tools and is
reported as an unsupported-format warning instead of failing the whole
scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_WORD_PATTERN = re.compile(r"\S+")

# Paragraph style names that InDesign templates in this project use for the
# "lead" (лід) paragraph, matched case-insensitively against the docx
# paragraph style name.
_LEAD_STYLE_HINTS = ("vrizka", "лід", "lead")

# When no reliable style information is available (e.g. plain .txt), a
# short standalone first paragraph is treated as a probable lead-in.
_LEAD_HEURISTIC_MAX_CHARS = 240


@dataclass
class TextMetrics:
    """Word/character counts and lead-paragraph detection for one article."""

    word_count: int = 0
    char_count: int = 0
    has_lead_paragraph: bool = False
    warnings: list[str] = field(default_factory=list)


def read_text_metrics(path: Path) -> TextMetrics:
    """Read ``path`` and compute its :class:`TextMetrics`.

    Never raises for expected failure modes (missing file, unsupported
    format, corrupt document) — instead returns zeroed metrics with a
    warning describing what went wrong, so a single bad file doesn't abort
    scanning the rest of the issue.
    """

    path = Path(path)
    suffix = path.suffix.lower()

    if not path.is_file():
        return TextMetrics(warnings=[f"Text file not found: {path}"])

    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".txt":
        return _read_txt(path)
    if suffix == ".doc":
        return TextMetrics(
            warnings=[
                "Legacy .doc format is not supported for automatic reading; "
                "please re-save as .docx"
            ]
        )
    return TextMetrics(warnings=[f"Unsupported text format: {suffix}"])


def _read_txt(path: Path) -> TextMetrics:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1251", errors="replace")
    except OSError as exc:
        return TextMetrics(warnings=[f"Could not read text file: {exc}"])

    paragraphs = [p for p in text.splitlines() if p.strip()]
    return _metrics_from_paragraphs(paragraphs, lead_style_hit=False, allow_heuristic=True)


def _read_docx(path: Path) -> TextMetrics:
    try:
        from docx import Document  # type: ignore[import-untyped]
    except ImportError:
        return TextMetrics(
            warnings=["python-docx is not installed; cannot read .docx files"]
        )

    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises varied/undocumented errors
        return TextMetrics(warnings=[f"Could not read .docx file: {exc}"])

    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]

    lead_style_hit = False
    for paragraph in document.paragraphs:
        if not paragraph.text.strip():
            continue
        style_name = (paragraph.style.name or "") if paragraph.style else ""
        lead_style_hit = any(hint in style_name.lower() for hint in _LEAD_STYLE_HINTS)
        break  # only the first non-empty paragraph counts as a possible lead

    return _metrics_from_paragraphs(paragraphs, lead_style_hit=lead_style_hit, allow_heuristic=False)


def _metrics_from_paragraphs(
    paragraphs: list[str], *, lead_style_hit: bool, allow_heuristic: bool
) -> TextMetrics:
    full_text = "\n".join(paragraphs)
    word_count = len(_WORD_PATTERN.findall(full_text))
    char_count = len(full_text)

    has_lead_paragraph = lead_style_hit
    if not has_lead_paragraph and allow_heuristic and len(paragraphs) > 1:
        has_lead_paragraph = 0 < len(paragraphs[0]) <= _LEAD_HEURISTIC_MAX_CHARS

    return TextMetrics(
        word_count=word_count,
        char_count=char_count,
        has_lead_paragraph=has_lead_paragraph,
    )
