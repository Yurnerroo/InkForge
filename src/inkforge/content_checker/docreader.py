"""Read structured text (title/lead/body) from an article's source document.

Supports ``.docx`` (via python-docx) and plain ``.txt``. Legacy ``.doc``
(binary Word format) cannot be parsed without external tools and is
reported as an unsupported-format warning instead of failing the whole
scan.

See ``docs/content-structure.md`` ("Структура тексту всередині файлу
статті") for the authoring convention this module implements: a paragraph
style is the primary signal, with a positional fallback when no
recognizable style is used (or for ``.txt``, which has no styles at all).

The positional fallback also supports **multiple articles in one file**,
separated only by one or more blank lines/paragraphs and detected by a
confirmed convention: a paragraph that does *not* end with a period is a
title (or, if it immediately follows another such paragraph, a
subheadline/lead); once real body text has started, another period-less
paragraph signals that a new article has begun. See
``read_text_metrics_multi``.
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

# Positional fallback (no recognizable style, or plain .txt) and
# multi-article splitting both rely on this confirmed convention: a
# paragraph is a title/subheadline if it does NOT end with a period;
# trailing closing quotes/brackets are ignored before the check.
_TRAILING_STRIP_CHARS = "\"'»)]” "


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
    """Read ``path`` and compute the :class:`ArticleText` for its FIRST
    article.

    Convenience wrapper around :func:`read_text_metrics_multi` for the
    common case of a file containing exactly one article. Files that may
    contain more than one article (see docs/content-structure.md, "Кілька
    статей в одному файлі") must use ``read_text_metrics_multi`` instead,
    or the extra articles are silently dropped.
    """

    results = read_text_metrics_multi(path)
    return results[0] if results else ArticleText()


def read_text_metrics_multi(path: Path) -> list[ArticleText]:
    """Read ``path`` and compute one :class:`ArticleText` per article found
    in it (almost always a single-element list).

    Never raises for expected failure modes (missing file, unsupported
    format, corrupt document) — instead returns a single-element list with
    a warning describing what went wrong, so a single bad file doesn't
    abort scanning the rest of the issue.
    """

    path = Path(path)
    suffix = path.suffix.lower()

    if not path.is_file():
        return [ArticleText(warnings=[f"Text file not found: {path}"])]

    if suffix == ".docx":
        return _read_docx_multi(path)
    if suffix == ".txt":
        return _read_txt_multi(path)
    if suffix == ".doc":
        return [
            ArticleText(
                warnings=[
                    "Legacy .doc format is not supported for automatic reading; "
                    "please re-save as .docx"
                ]
            )
        ]
    return [ArticleText(warnings=[f"Unsupported text format: {suffix}"])]


def _read_txt_multi(path: Path) -> list[ArticleText]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1251", errors="replace")
    except OSError as exc:
        return [ArticleText(warnings=[f"Could not read text file: {exc}"])]

    paragraphs = [p for p in text.splitlines() if p.strip()]
    splits = _split_positional_multi(paragraphs)
    if not splits:
        return [ArticleText()]
    return [_build_result(title, lead, body) for title, lead, body in splits]


def _read_docx_multi(path: Path) -> list[ArticleText]:
    try:
        from docx import Document  # type: ignore[import-untyped]
    except ImportError:
        return [
            ArticleText(warnings=["python-docx is not installed; cannot read .docx files"])
        ]

    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises varied/undocumented errors
        return [ArticleText(warnings=[f"Could not read .docx file: {exc}"])]

    non_empty = [p for p in document.paragraphs if p.text.strip()]
    paragraphs = [p.text.strip() for p in non_empty]

    title_idx = _find_style_match(non_empty, _TITLE_STYLE_HINTS)
    lead_idx = _find_style_match(non_empty, _LEAD_STYLE_HINTS)

    if title_idx is not None or lead_idx is not None:
        # Named-style path stays single-article: splitting several
        # style-tagged articles out of one file hasn't been confirmed as a
        # real scenario, so we don't guess at it here.
        title = paragraphs[title_idx] if title_idx is not None else ""
        lead = paragraphs[lead_idx] if lead_idx is not None else ""
        skip = {i for i in (title_idx, lead_idx) if i is not None}
        body = "\n".join(p for i, p in enumerate(paragraphs) if i not in skip)
        return [_build_result(title, lead, body)]

    splits = _split_positional_multi(paragraphs)
    warnings = []
    if paragraphs:
        warnings.append(
            "No recognized title/lead paragraph style found; used positional "
            "fallback (first paragraph = title, second = lead if it also "
            "lacks a trailing period) — please double-check the split"
        )
    if not splits:
        return [_build_result("", "", "", warnings=warnings)]
    results = [_build_result(title, lead, body) for title, lead, body in splits]
    for result in results:
        result.warnings = warnings + result.warnings
    return results


def _find_style_match(paragraphs: list, hints: tuple[str, ...]) -> int | None:
    """Return the index of the first paragraph whose style name matches one
    of ``hints`` (case-insensitive substring), or ``None`` if none match."""

    for i, paragraph in enumerate(paragraphs):
        style_name = (paragraph.style.name or "") if paragraph.style else ""
        if any(hint in style_name.lower() for hint in hints):
            return i
    return None


def _ends_with_period(text: str) -> bool:
    """True if ``text``'s last "real" character is a period -- the
    confirmed signal that a paragraph is body text rather than a
    title/subheadline. Trailing closing quotes/brackets/whitespace are
    stripped first so ``Заголовок."`` is still recognized correctly."""

    stripped = text.rstrip().rstrip(_TRAILING_STRIP_CHARS)
    return stripped.endswith(".")


def _split_positional_multi(paragraphs: list[str]) -> list[tuple[str, str, str]]:
    """Split ``paragraphs`` into one or more articles using the confirmed
    convention (docs/content-structure.md, "Кілька статей в одному файлі"):

    - The first paragraph of each article is its title (unconditionally
      for the very first paragraph of the file; for subsequent articles,
      a period-less paragraph encountered once body text has started is
      what signals a new title).
    - If the paragraph right after a title also lacks a trailing period,
      it's that article's lead/subheadline.
    - Everything else is body, accumulated until the next title-like
      paragraph appears. Blank lines/paragraphs between articles are
      irrelevant here -- they're already filtered out before this
      function runs -- so one or two blank lines both work the same way.
    """

    if not paragraphs:
        return []

    def consume_lead(i: int, lead_holder: list[str]) -> int:
        if i < len(paragraphs) and not _ends_with_period(paragraphs[i]):
            lead_holder.append(paragraphs[i])
            return i + 1
        return i

    articles: list[tuple[str, str, str]] = []
    title = paragraphs[0]
    lead_holder: list[str] = []
    i = consume_lead(1, lead_holder)
    body_parts: list[str] = []

    while i < len(paragraphs):
        para = paragraphs[i]
        if body_parts and not _ends_with_period(para):
            # Body text already started, and this paragraph doesn't end
            # with a period -- a new article begins here.
            articles.append((title, lead_holder[0] if lead_holder else "", "\n".join(body_parts)))
            title = para
            lead_holder = []
            body_parts = []
            i = consume_lead(i + 1, lead_holder)
            continue
        body_parts.append(para)
        i += 1

    articles.append((title, lead_holder[0] if lead_holder else "", "\n".join(body_parts)))
    return articles


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
