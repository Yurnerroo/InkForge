"""Tests for inkforge.layout_engine.profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from inkforge.layout_engine.profile import (
    ProfileError,
    load_profile,
    load_profile_by_id,
    resolve_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "profiles"

MINIMAL_YAML = """
id: test_gazeta
display_name: "Test Gazeta"
page_count: 4
manual_pages: [1, 4]
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
notes: "test fixture"
"""


def test_load_profile_parses_all_fields(tmp_path: Path) -> None:
    profile_path = tmp_path / "test_gazeta.yaml"
    profile_path.write_text(MINIMAL_YAML, encoding="utf-8")

    profile = load_profile(profile_path)

    assert profile.id == "test_gazeta"
    assert profile.page_count == 4
    assert profile.manual_pages == [1, 4]
    assert profile.spreads[0].pages == [2, 3]
    assert profile.spreads[0].color_mode == "grayscale"
    assert profile.photo_links.storage == "linked"
    assert profile.cmyk_profile is None
    assert profile.character_size_roles is None
    assert profile.headline_font_alternation is None


def test_color_mode_for_page(tmp_path: Path) -> None:
    profile_path = tmp_path / "test_gazeta.yaml"
    profile_path.write_text(MINIMAL_YAML, encoding="utf-8")
    profile = load_profile(profile_path)

    assert profile.color_mode_for_page(2) == "grayscale"
    assert profile.color_mode_for_page(3) == "grayscale"
    assert profile.color_mode_for_page(1) is None
    assert profile.is_manual(1) is True
    assert profile.is_manual(2) is False


def test_load_profile_missing_field_raises(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("id: broken\ndisplay_name: Broken\n", encoding="utf-8")

    with pytest.raises(ProfileError, match="page_count"):
        load_profile(broken)


def test_load_profile_not_a_mapping_raises(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ProfileError):
        load_profile(broken)


def test_load_profile_by_id_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="не знайдено"):
        load_profile_by_id("nonexistent", tmp_path)


def test_resolve_profile_by_direct_path(tmp_path: Path) -> None:
    profile_path = tmp_path / "somewhere.yaml"
    profile_path.write_text(MINIMAL_YAML, encoding="utf-8")

    profile = resolve_profile(str(profile_path), profiles_dir=tmp_path / "unused")

    assert profile.id == "test_gazeta"


def test_resolve_profile_by_id(tmp_path: Path) -> None:
    (tmp_path / "test_gazeta.yaml").write_text(MINIMAL_YAML, encoding="utf-8")

    profile = resolve_profile("test_gazeta", profiles_dir=tmp_path)

    assert profile.id == "test_gazeta"


@pytest.mark.parametrize("newspaper_id", ["ty_i_ya", "mif", "dyhovnist"])
def test_real_profiles_load_successfully(newspaper_id: str) -> None:
    """The 3 profiles merged into the repo must all parse and be internally consistent."""

    profile = load_profile_by_id(newspaper_id, PROFILES_DIR)

    assert profile.id == newspaper_id
    assert profile.page_count > 0
    for spread in profile.spreads:
        assert spread.color_mode in {"grayscale", "cmyk", "mixed"}
    for page in profile.manual_pages:
        assert 1 <= page <= profile.page_count


def test_dyhovnist_profile_carries_character_size_roles_fallback() -> None:
    """Dyhovnist has no reliable paragraph_style_roles, so it must fall back
    to character_size_roles (see profiles/dyhovnist.yaml notes)."""

    profile = load_profile_by_id("dyhovnist", PROFILES_DIR)

    assert profile.paragraph_style_roles == "TBD"
    assert profile.character_size_roles is not None
    assert profile.character_size_roles["method"] == "character_point_size"
    assert profile.character_size_roles["body_point_size_max"] < profile.character_size_roles["headline_like_point_size_min"]


def test_ty_i_ya_profile_carries_headline_font_alternation() -> None:
    """Ty i Ya has a confirmed headline-font-alternation rule (see
    profiles/ty_i_ya.yaml notes) — should surface as a structured field,
    not just prose in `notes`."""

    profile = load_profile_by_id("ty_i_ya", PROFILES_DIR)

    assert profile.headline_font_alternation is not None
    assert profile.headline_font_alternation["confirmed"] is True
    assert len(profile.headline_font_alternation["fonts"]) == 2


@pytest.mark.parametrize("newspaper_id", ["mif", "dyhovnist"])
def test_other_profiles_default_headline_font_alternation_to_none(newspaper_id: str) -> None:
    """MIF and Dyhovnist have no confirmed headline-font-alternation rule yet
    — must not be guessed, so the field stays None."""

    profile = load_profile_by_id(newspaper_id, PROFILES_DIR)

    assert profile.headline_font_alternation is None
