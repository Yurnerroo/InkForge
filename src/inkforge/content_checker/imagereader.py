"""Read basic metadata from an article's photo file."""

from __future__ import annotations

from pathlib import Path

from .models import ImageInfo

DEFAULT_MIN_DPI = 200.0
"""Newsprint reproduction rule of thumb: photos below this are flagged as
suspiciously low resolution. This is a placeholder — adjust once the real
print requirement is confirmed against the newspaper's ``.joboptions``."""


def read_image_info(path: Path, *, min_dpi: float = DEFAULT_MIN_DPI) -> ImageInfo | None:
    """Read ``path`` and return its :class:`~inkforge.content_checker.models.ImageInfo`.

    Returns ``None`` (rather than raising) if the file cannot be opened as an
    image at all — missing, corrupt, or not actually an image. The caller
    already has the article context and is expected to add its own warning
    for that case.
    """

    path = Path(path)

    try:
        from PIL import Image
    except ImportError:
        return ImageInfo(
            path=path,
            width=0,
            height=0,
            dpi=None,
            color_mode="",
            warnings=["Pillow is not installed; cannot read image metadata"],
        )

    try:
        with Image.open(path) as img:
            width, height = img.size
            color_mode = img.mode
            dpi = img.info.get("dpi")
    except Exception:
        return None

    warnings: list[str] = []
    if not dpi:
        warnings.append("Photo has no embedded DPI metadata; resolution cannot be checked")
        dpi = None
    else:
        effective_dpi = min(dpi)
        if effective_dpi < min_dpi:
            warnings.append(
                f"Photo resolution looks low: {effective_dpi:.0f} DPI "
                f"(expected at least {min_dpi:.0f})"
            )

    return ImageInfo(
        path=path,
        width=width,
        height=height,
        dpi=tuple(dpi) if dpi else None,
        color_mode=color_mode,
        warnings=warnings,
    )
