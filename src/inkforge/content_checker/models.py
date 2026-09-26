"""Data models describing a scanned weekly issue."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImageInfo:
    """Metadata extracted from a photo file."""

    path: Path
    width: int
    height: int
    dpi: tuple[float, float] | None
    color_mode: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ArticleContent:
    """One article: its text file, optional photo, and derived metrics."""

    page: str
    order: int
    slug: str
    text_path: Path | None = None
    image_path: Path | None = None
    image_info: ImageInfo | None = None
    word_count: int = 0
    char_count: int = 0
    has_lead_paragraph: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def article_id(self) -> str:
        return f"{self.page}_{self.order}_{self.slug}"


@dataclass
class PageContent:
    """All articles pre-assigned to a single page of the issue."""

    page: str
    articles: list[ArticleContent] = field(default_factory=list)
    folder_warnings: list[str] = field(default_factory=list)
    """Warnings not tied to one specific article, e.g. an unrecognized file
    or a file name that doesn't match the naming convention."""

    @property
    def total_word_count(self) -> int:
        return sum(article.word_count for article in self.articles)


@dataclass
class IssueContent:
    """The full scanned weekly issue: every page and its articles."""

    root: Path
    newspaper: str = ""
    pages: list[PageContent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_warnings(self) -> list[str]:
        collected = list(self.warnings)
        for page in self.pages:
            collected.extend(f"[{page.page}] {w}" for w in page.folder_warnings)
            for article in page.articles:
                collected.extend(
                    f"[{page.page}/{article.article_id}] {w}" for w in article.warnings
                )
        return collected
