"""Read structured text (title/lead/body) from an article's source document.

Supports ``.docx`` (via python-docx) and plain ``.txt``. Legacy ``.doc``
(binary Word format) cannot be parsed without external tools and is
reported as an unsupported-format warning instead of failing the whole
scan.

See ``docs/content-structure.md`` ("Структура тексту всередині файлу
статті") for the authoring convention this module implements: a paragraph
style is the primary signal, with a positional fallback when no
recognizable style is used (or for ``.txt``, which has no styles at all).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_WORD_PATTERN = re.compile(r"\S+")

# Paragraph style name hints (docx), matched case-insensitively as a
# substring against the paragraph's style name. See docs/content-structure.md
# for the authoring convention these encode.
_TITLE_STYLE_HINTS = ("заголовок", "title", "heading")
_LEAD_STYLE_HINTS = ("лід", "лид", "vrizka", "lead")

# Positional fallback (no recognizable style, or plain .txt): a short
# second line/paragraph is treated as a probable lead-in.
_LEAD_HEURISTIC_MAX_CHARS = 240


@dataclass
class ArticleText:
    """Structured title/lead/body plus aggregate metrics for one article."""

    title: str = ""
    lead: str = ""
    body: str = ""
    word_count: int = 0
    char_count: int = 0
    has_lead_paragraph: bool = False
    warnings: list[str] = field(default_factory=list)


def read_text_metrics(path: Path) -> ArticleText:
    """Read ``path`` and compute its :class:`ArticleText`.

    Never raises for expected failure modes (missing file, unsupported
    format, corrupt document) — instead returns an empty result with a
    warning describing what went wrong, so a single bad file doesn't abort
    scanning the rest of the issue.
    """

    path = Path(path)
    suffix = path.suffix.lower()

    if not path.is_file():
        return ArticleText(warnings=[f"Text file not found: {path}"])

    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".txt":
        return _read_txt(path)
    if suffix == ".doc":
        return ArticleText(
            warnings=[
                "Legacy .doc format is not supported for automatic reading; "
                "please re-save as .docx"
            ]
        )
    return ArticleText(warnings=[f"Unsupported text format: {suffix}"])


def _read_txt(path: Path) -> ArticleText:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1251", errors="replace")
    except OSError as exc:
        return ArticleText(warnings=[f"Could not read text file: {exc}"])

    paragraphs = [p for p in text.splitlines() if p.strip()]
    title, lead, body = _split_positional(paragraphs)
    return _build_result(title, lead, body)


def _read_docx(path: Path) -> ArticleText:
    try:
        from docx import Document  # type: ignore[import-untyped]
    except ImportError:
        return ArticleText(
            warnings=["python-docx is not installed; cannot read .docx files"]
        )

    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises varied/undocumented errors
        return ArticleText(warnings=[f"Could not read .docx file: {exc}"])

    non_empty = [p for p in document.paragraphs if p.text.strip()]
    paragraphs = [p.text.strip() for p in non_empty]

    title_idx = _find_style_match(non_empty, _TITLE_STYLE_HINTS)
    lead_idx = _find_style_match(non_empty, _LEAD_STYLE_HINTS)

    if title_idx is not None or lead_idx is not None:
        title = paragraphs[title_idx] if title_idx is not None else ""
        lead = paragraphs[lead_idx] if lead_idx is not None else ""
        skip = {i for i in (title_idx, lead_idx) if i is not None}
        body = "\n".join(p for i, p in enumerate(paragraphs) if i not in skip)
        return _build_result(title, lead, body)

    title, lead, body = _split_positional(paragraphs)
    warnings = []
    if paragraphs:
        warnings.append(
            "No recognized title/lead paragraph style found; used positional "
            "fallback (first paragraph = title, short second = lead) — "
            "please double-check the split"
        )
    return _build_result(title, lead, body, warnings=warnings)


def _find_style_match(paragraphs: list, hints: tuple[str, ...]) -> int | None:
    """Return the index of the first paragraph whose style name matches one
    of ``hints`` (case-insensitive substring), or ``None`` if none match."""

    for i, paragraph in enumerate(paragraphs):
        style_name = (paragraph.style.name or "") if paragraph.style else ""
        if any(hint in style_name.lower() for hint in hints):
            return i
    return None


def _split_positional(paragraphs: list[str]) -> tuple[str, str, str]:
    """Positional title/lead/body split used when no style info is
    available (``.txt``, or ``.docx`` with no recognized styles)."""

    if not paragraphs:
        return "", "", ""
    if len(paragraphs) == 1:
        return paragraphs[0], "", ""

    title = paragraphs[0]
    rest = paragraphs[1:]
    if len(rest) >= 2 and 0 < len(rest[0]) <= _LEAD_HEURISTIC_MAX_CHARS:
        return title, rest[0], "\n".join(rest[1:])
    return title, "", "\n".join(rest)


def _build_result(title: str, lead: str, body: str, *, warnings: list[str] | None = None) -> ArticleText:
    full_text = "\n".join(p for p in (title, lead, body) if p)
    word_count = len(_WORD_PATTERN.findall(full_text))
    char_count = len(full_text)

    return ArticleText(
        title=title,
        lead=lead,
        body=body,
        word_count=word_count,
        char_count=char_count,
        has_lead_paragraph=bool(lead),
        warnings=list(warnings or []),
    )
