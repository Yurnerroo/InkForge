"""Load and validate per-newspaper Level 2 profiles.

See ``profiles/schema.md`` for the authoritative field-by-field description.
Nothing in Level 2's shared code should hardcode a style/frame name or color
pattern -- it all comes from a profile loaded here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProfileError(ValueError):
    """Raised when a profile file is missing, malformed, or missing fields."""


@dataclass
class Spread:
    """One spread (two-page opening), e.g. ``{pages: [2, 3], color_mode: grayscale}``."""

    pages: list[int]
    color_mode: str


@dataclass
class SpecialPage:
    """A page with non-standard structure, e.g. a TV-programme page."""

    pages: list[int]
    description: str
    automation: str


@dataclass
class PhotoLinks:
    storage: str
    naming_pattern: str


@dataclass
class NewspaperProfile:
    """Everything Level 2 needs to know about one newspaper template."""

    id: str
    display_name: str
    page_count: int
    manual_pages: list[int]
    manual_pages_uncertain: list[int]
    spreads: list[Spread]
    color_alternation_pattern: str
    cmyk_profile: str | None
    photo_links: PhotoLinks
    paragraph_styles_found: list[str]
    paragraph_style_roles: dict[str, list[str]] | str
    special_pages: list[SpecialPage]
    fonts_installed: list[str]
    fonts_substituted: list[str]
    frame_stability: str
    samples_analyzed: list[str]
    notes: str

    def color_mode_for_page(self, page: int) -> str | None:
        """Return the spread's color mode for ``page``, or None if unknown."""

        for spread in self.spreads:
            if page in spread.pages:
                return spread.color_mode
        return None

    def is_manual(self, page: int) -> bool:
        return page in self.manual_pages

    def is_uncertain(self, page: int) -> bool:
        return page in self.manual_pages_uncertain

    def special_page_for(self, page: int) -> SpecialPage | None:
        for special_page in self.special_pages:
            if page in special_page.pages:
                return special_page
        return None


REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "display_name",
    "page_count",
    "manual_pages",
    "manual_pages_uncertain",
    "spreads",
    "color_alternation_pattern",
    "cmyk_profile",
    "photo_links",
    "paragraph_styles_found",
    "paragraph_style_roles",
    "special_pages",
    "fonts_installed",
    "fonts_substituted",
    "frame_stability",
    "samples_analyzed",
    "notes",
)


def load_profile(path: Path) -> NewspaperProfile:
    """Load and validate a single ``profiles/<id>.yaml`` file."""

    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"Профіль {path} не є коректним YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ProfileError(f"Профіль {path} має бути YAML-об'єктом верхнього рівня")

    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        raise ProfileError(
            f"Профіль {path} не містить обов'язкові поля: {', '.join(missing)}"
        )

    return _profile_from_dict(raw)


def load_profile_by_id(newspaper_id: str, profiles_dir: Path) -> NewspaperProfile:
    """Load ``profiles_dir/<newspaper_id>.yaml``."""

    path = Path(profiles_dir) / f"{newspaper_id}.yaml"
    if not path.is_file():
        raise ProfileError(f"Профіль для газети '{newspaper_id}' не знайдено: {path}")
    return load_profile(path)


def resolve_profile(profile_arg: str, profiles_dir: Path) -> NewspaperProfile:
    """Resolve a CLI ``--profile`` argument.

    ``profile_arg`` is either a direct path to a ``.yaml``/``.yml`` file, or a
    newspaper id looked up as ``profiles_dir/<profile_arg>.yaml``.
    """

    candidate = Path(profile_arg)
    if candidate.suffix.lower() in {".yaml", ".yml"} and candidate.is_file():
        return load_profile(candidate)
    return load_profile_by_id(profile_arg, profiles_dir)


def _profile_from_dict(raw: dict[str, Any]) -> NewspaperProfile:
    photo_links_raw = raw["photo_links"]
    try:
        photo_links = PhotoLinks(
            storage=photo_links_raw["storage"],
            naming_pattern=photo_links_raw["naming_pattern"],
        )
    except (KeyError, TypeError) as exc:
        raise ProfileError(f"Некоректне поле photo_links: {photo_links_raw!r}") from exc

    try:
        spreads = [
            Spread(pages=list(item["pages"]), color_mode=item["color_mode"])
            for item in raw["spreads"]
        ]
    except (KeyError, TypeError) as exc:
        raise ProfileError(f"Некоректне поле spreads: {raw['spreads']!r}") from exc

    try:
        special_pages = [
            SpecialPage(
                pages=list(item["pages"]),
                description=item["description"],
                automation=item["automation"],
            )
            for item in raw.get("special_pages") or []
        ]
    except (KeyError, TypeError) as exc:
        raise ProfileError(f"Некоректне поле special_pages: {raw.get('special_pages')!r}") from exc

    return NewspaperProfile(
        id=raw["id"],
        display_name=raw["display_name"],
        page_count=raw["page_count"],
        manual_pages=list(raw["manual_pages"]),
        manual_pages_uncertain=list(raw["manual_pages_uncertain"]),
        spreads=spreads,
        color_alternation_pattern=raw["color_alternation_pattern"],
        cmyk_profile=raw["cmyk_profile"],
        photo_links=photo_links,
        paragraph_styles_found=list(raw["paragraph_styles_found"]),
        paragraph_style_roles=raw["paragraph_style_roles"],
        special_pages=special_pages,
        fonts_installed=list(raw["fonts_installed"]),
        fonts_substituted=list(raw["fonts_substituted"]),
        frame_stability=raw["frame_stability"],
        samples_analyzed=list(raw["samples_analyzed"]),
        notes=raw["notes"],
    )
