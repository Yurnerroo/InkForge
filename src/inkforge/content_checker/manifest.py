"""Build the ``manifest.json`` consumed by Level 2 (InDesign auto-layout)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ArticleContent, ImageInfo, IssueContent


def build_manifest(issue: IssueContent) -> dict[str, Any]:
    """Serialize ``issue`` into a JSON-ready dict."""

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(issue.root),
        "newspaper": issue.newspaper,
        "pages": [
            {
                "page": page.page,
                "total_word_count": page.total_word_count,
                "folder_warnings": list(page.folder_warnings),
                "articles": [_article_to_dict(article) for article in page.articles],
            }
            for page in issue.pages
        ],
        "warnings": list(issue.all_warnings),
    }


def write_manifest(issue: IssueContent, path: Path) -> None:
    """Write ``build_manifest(issue)`` as pretty-printed JSON to ``path``."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(issue)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _article_to_dict(article: ArticleContent) -> dict[str, Any]:
    return {
        "article_id": article.article_id,
        "page": article.page,
        "order": article.order,
        "sub_order": article.sub_order,
        "slug": article.slug,
        "text_path": _optional_str(article.text_path),
        "image_path": _optional_str(article.image_path),
        "image": _image_to_dict(article.image_info),
        "title": article.title,
        "lead": article.lead,
        "body": article.body,
        "word_count": article.word_count,
        "char_count": article.char_count,
        "has_lead_paragraph": article.has_lead_paragraph,
        "warnings": list(article.warnings),
    }


def _image_to_dict(image: ImageInfo | None) -> dict[str, Any] | None:
    if image is None:
        return None
    return {
        "width": image.width,
        "height": image.height,
        "dpi": list(image.dpi) if image.dpi else None,
        "color_mode": image.color_mode,
    }


def _optional_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None
