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

from .docreader import read_text_metrics_multi
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

        order = int(match.group("order"))
        slug = match.group("slug")
        stem_page = match.group("page")

        base_warnings: list[str] = []
        try:
            if int(stem_page) != int(folder.name):
                base_warnings.append(
                    f"File prefix page '{stem_page}' differs from folder page '{folder.name}'"
                )
        except ValueError:
            base_warnings.append(
                f"Could not compare file prefix page '{stem_page}' with folder page '{folder.name}'"
            )

        if order in seen_orders:
            base_warnings.append(
                f"Duplicate article order {order} on this page (also used by '{seen_orders[order]}')"
            )
        else:
            seen_orders[order] = stem

        image_path = files.get("image")
        image_info = None
        image_warnings: list[str] = []
        if image_path is not None:
            image_info = read_image_info(image_path)
            if image_info is None:
                image_warnings.append(f"Could not read image file: {image_path.name}")
            else:
                image_warnings.extend(image_info.warnings)

        text_path = files.get("text")
        if text_path is None:
            article = ArticleContent(
                page=folder.name,
                order=order,
                slug=slug,
                image_path=image_path,
                image_info=image_info,
            )
            article.warnings.extend(base_warnings)
            article.warnings.append("Photo found without a matching text file")
            article.warnings.extend(image_warnings)
            page.articles.append(article)
            continue

        texts = read_text_metrics_multi(text_path)
        multi = len(texts) > 1
        for sub_order, text in enumerate(texts):
            # The shared photo file (if any) is only attached to the first
            # split article -- we don't know which one it actually depicts,
            # so we don't guess by attaching it to all of them.
            is_first = sub_order == 0
            article = ArticleContent(
                page=folder.name,
                order=order,
                slug=slug,
                sub_order=sub_order,
                text_path=text_path,
                image_path=image_path if is_first else None,
                image_info=image_info if is_first else None,
                title=text.title,
                lead=text.lead,
                body=text.body,
                word_count=text.word_count,
                char_count=text.char_count,
                has_lead_paragraph=text.has_lead_paragraph,
            )
            article.warnings.extend(base_warnings)
            article.warnings.extend(text.warnings)
            if is_first:
                article.warnings.extend(image_warnings)
            if multi:
                article.warnings.append(
                    f"Split from a multi-article file (part {sub_order + 1} of {len(texts)})"
                )
            page.articles.append(article)

    page.articles.sort(key=lambda a: (a.order, a.sub_order))
    return page
