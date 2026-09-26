"""Scan a weekly issue folder and build :class:`IssueContent`.

Expected folder layout (see docs/content-structure.md for the full spec)::

    2026-W40_gazeta-x/
      01/
        1_1_lider-tyzhnya.docx
        1_1_lider-tyzhnya.jpg
        1_2_korotko.docx
      02/
        2_1_sport.docx
        2_1_sport.jpg

Each file's stem must match ``{page}_{order}_{slug}``. ``page`` in the
stem should agree with the page-folder's number; a mismatch is reported
as a warning rather than a hard failure, since the layout can still
proceed with the folder name taken as authoritative.
"""

from __future__ import annotations

import re
from pathlib import Path

from .docreader import read_text_metrics
from .imagereader import read_image_info
from .models import ArticleContent, IssueContent, PageContent

TEXT_EXTENSIONS = {".docx", ".doc", ".txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

_STEM_PATTERN = re.compile(r"^(?P<page>\d+)_(?P<order>\d+)_(?P<slug>.+)$")


def _iter_page_folders(root: Path) -> list[Path]:
    folders = [p for p in root.iterdir() if p.is_dir()]

    def sort_key(p: Path) -> tuple[int, str]:
        try:
            return (0, f"{int(p.name):04d}")
        except ValueError:
            return (1, p.name)

    return sorted(folders, key=sort_key)


def scan_issue(root: Path, newspaper: str = "") -> IssueContent:
    """Scan ``root`` (a weekly issue folder) and return its parsed content."""

    root = Path(root)
    issue = IssueContent(root=root, newspaper=newspaper)

    if not root.is_dir():
        issue.warnings.append(f"Issue folder not found: {root}")
        return issue

    for folder in _iter_page_folders(root):
        issue.pages.append(_scan_page_folder(folder))

    return issue


def _scan_page_folder(folder: Path) -> PageContent:
    page = PageContent(page=folder.name)

    grouped: dict[str, dict[str, Path]] = {}
    for file in sorted(folder.iterdir()):
        if not file.is_file():
            continue
        stem, suffix = file.stem, file.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            grouped.setdefault(stem, {})["text"] = file
        elif suffix in IMAGE_EXTENSIONS:
            grouped.setdefault(stem, {})["image"] = file
        else:
            page.folder_warnings.append(f"Unrecognized file skipped: {file.name}")

    seen_orders: dict[int, str] = {}
    for stem, files in sorted(grouped.items()):
        match = _STEM_PATTERN.match(stem)
        if not match:
            page.folder_warnings.append(
                f"File name doesn't match '{{page}}_{{order}}_{{slug}}' pattern: {stem}"
            )
            continue

        article = ArticleContent(
            page=folder.name,
            order=int(match.group("order")),
            slug=match.group("slug"),
            text_path=files.get("text"),
            image_path=files.get("image"),
        )

        stem_page = match.group("page")
        try:
            if int(stem_page) != int(folder.name):
                article.warnings.append(
                    f"File prefix page '{stem_page}' differs from folder page '{folder.name}'"
                )
        except ValueError:
            article.warnings.append(
                f"Could not compare file prefix page '{stem_page}' with folder page '{folder.name}'"
            )

        if article.order in seen_orders:
            article.warnings.append(
                f"Duplicate article order {article.order} on this page "
                f"(also used by '{seen_orders[article.order]}')"
            )
        else:
            seen_orders[article.order] = stem

        if article.text_path is None:
            article.warnings.append("Photo found without a matching text file")
        else:
            metrics = read_text_metrics(article.text_path)
            article.word_count = metrics.word_count
            article.char_count = metrics.char_count
            article.has_lead_paragraph = metrics.has_lead_paragraph
            article.warnings.extend(metrics.warnings)

        if article.image_path is not None:
            article.image_info = read_image_info(article.image_path)
            if article.image_info is None:
                article.warnings.append(
                    f"Could not read image file: {article.image_path.name}"
                )
            else:
                article.warnings.extend(article.image_info.warnings)

        page.articles.append(article)

    page.articles.sort(key=lambda a: a.order)
    return page
