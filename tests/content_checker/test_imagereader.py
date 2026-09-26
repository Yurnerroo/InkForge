from pathlib import Path

from PIL import Image

from inkforge.content_checker.imagereader import read_image_info


def test_read_image_info_basic_metadata(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (400, 300)).save(path, dpi=(300, 300))

    info = read_image_info(path)

    assert info is not None
    assert info.width == 400
    assert info.height == 300
    assert info.dpi is not None
    assert all(abs(d - 300) < 1 for d in info.dpi)
    assert info.color_mode == "RGB"
    assert info.warnings == []


def test_read_image_info_flags_low_dpi(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (100, 100)).save(path, dpi=(72, 72))

    info = read_image_info(path, min_dpi=200)

    assert info is not None
    assert any("low" in w.lower() for w in info.warnings)


def test_read_image_info_flags_missing_dpi(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (100, 100)).save(path)  # no dpi info embedded

    info = read_image_info(path)

    assert info is not None
    assert info.dpi is None
    assert any("no embedded DPI" in w for w in info.warnings)


def test_read_image_info_missing_file_returns_none(tmp_path: Path) -> None:
    info = read_image_info(tmp_path / "missing.png")

    assert info is None


def test_read_image_info_corrupt_file_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not-actually-an-image")

    info = read_image_info(path)

    assert info is None


def test_read_image_info_normalizes_ifdrational_dpi_to_float(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression test: real-world JPEGs with EXIF-only resolution tags (no
    JFIF header) make Pillow report dpi as IFDRational, which broke JSON
    serialization of the manifest ("Object of type IFDRational is not JSON
    serializable")."""

    from PIL.TiffImagePlugin import IFDRational

    path = tmp_path / "photo.jpg"
    Image.new("RGB", (100, 100)).save(path)

    real_open = Image.open

    class _FakeImg:
        def __init__(self, img):
            self._img = img
            self.size = img.size
            self.mode = img.mode
            self.info = {"dpi": (IFDRational(300, 1), IFDRational(300, 1))}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._img.close()

    def fake_open(p):
        return _FakeImg(real_open(p))

    monkeypatch.setattr(Image, "open", fake_open)

    info = read_image_info(path)

    assert info is not None
    assert info.dpi == (300.0, 300.0)
    assert all(isinstance(d, float) for d in info.dpi)
    import json

    json.dumps({"dpi": info.dpi})  # must not raise
