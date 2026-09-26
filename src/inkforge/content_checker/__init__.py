"""Level 1: Content Checker.

Scans a weekly issue folder, matches article text files with their
photos by filename, measures content volume, and produces a
``manifest.json`` that downstream tools (the InDesign auto-layout
script, Level 2) consume.
"""

from .manifest import build_manifest, write_manifest
from .models import ArticleContent, IssueContent, PageContent
from .report import render_report
from .scanner import scan_issue

__all__ = [
    "ArticleContent",
    "IssueContent",
    "PageContent",
    "build_manifest",
    "render_report",
    "scan_issue",
    "write_manifest",
]
