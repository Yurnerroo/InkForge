"""Tests for inkforge.layout_engine.cli."""

from __future__ import annotations

import json
from pathlib import Path

from inkforge.layout_engine.cli import main

PROFILE_YAML = """
id: test_gazeta
display_name: "Test Gazeta"
page_count: 3
manual_pages: [1]
manual_pages_uncertain: []
spreads:
  - pages: [2, 3]
    color_mode: grayscale
color_alternation_pattern: "n/a"
cmyk_profile: null
photo_links:
  storage: linked
  naming_pattern: "Links/{page}.{ext}"
paragraph_styles_found: [Body]
paragraph_style_roles:
  body: [Body]
special_pages: []
fonts_installed: [Arial]
fonts_substituted: []
frame_stability: partial
samples_analyzed: [issue01]
notes: ""
"""


def _write_manifest(path: Path) -> None:
    manifest = {
        "root": str(path.parent),
        "pages": [
            {
                "page": "2",
                "articles": [
                    {"article_id": "2_1_a", "order": 1, "slug": "a", "word_count": 10, "image": None}
                ],
            }
        ],
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def test_cli_writes_layout_plan(tmp_path: Path, capsys) -> None:
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "test_gazeta.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path)

    exit_code = main(
        [str(manifest_path), "--profile", "test_gazeta", "--profiles-dir", str(profiles_dir)]
    )

    assert exit_code == 0
    plan_path = tmp_path / "layout_plan.json"
    assert plan_path.is_file()
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    assert data["newspaper_id"] == "test_gazeta"
    captured = capsys.readouterr()
    assert "Test Gazeta" in captured.out


def test_cli_missing_manifest_returns_error(tmp_path: Path) -> None:
    exit_code = main([str(tmp_path / "nope.json"), "--profile", "test_gazeta"])

    assert exit_code == 2


def test_cli_unknown_profile_returns_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path)

    exit_code = main([str(manifest_path), "--profile", "nonexistent", "--profiles-dir", str(tmp_path)])

    assert exit_code == 2
