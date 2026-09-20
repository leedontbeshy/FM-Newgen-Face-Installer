import pytest
from PIL import Image

from core.image_manager import ImageError, preview_image, stage_png, validate_image


@pytest.mark.parametrize(
    "extension,format_,mode",
    [("jpg", "JPEG", "RGB"), ("jpeg", "JPEG", "RGB"), ("webp", "WEBP", "RGBA"), ("png", "PNG", "RGBA")],
)
def test_conversion_preserves_dimensions_and_alpha(tmp_path, extension, format_, mode):
    source = tmp_path / f"face.{extension}"
    color = (120, 80, 40, 77) if mode == "RGBA" else (120, 80, 40)
    Image.new(mode, (117, 203), color).save(source, format=format_)
    output = stage_png(source, tmp_path)
    try:
        with Image.open(output) as image:
            assert image.format == "PNG" and image.size == (117, 203)
            if mode == "RGBA":
                assert image.getpixel((0, 0))[3] == 77
        if format_ == "PNG":
            assert output.read_bytes() == source.read_bytes()
    finally:
        output.unlink()


def test_palette_transparency_png_preserved(tmp_path):
    source = tmp_path / "palette.png"
    image = Image.new("P", (9, 13))
    image.info["transparency"] = 0
    image.save(source)
    output = stage_png(source, tmp_path)
    assert source.read_bytes() == output.read_bytes()


def test_jpeg_exif_orientation(tmp_path):
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (40, 80))
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, exif=exif)
    output = stage_png(source, tmp_path)
    with Image.open(output) as result:
        assert result.size == (80, 40)


def test_preview_does_not_change_source(tmp_path):
    source = tmp_path / "face.png"
    Image.new("RGBA", (400, 800)).save(source)
    before = source.read_bytes()
    preview, full_size = preview_image(source, (200, 200))
    assert preview.size == (100, 200) and full_size == (400, 800)
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "name,contents", [("broken.png", b"garbage"), ("face.gif", b"GIF89a"), ("missing.jpg", None)]
)
def test_unreadable_or_unsupported(tmp_path, name, contents):
    path = tmp_path / name
    if contents:
        path.write_bytes(contents)
    with pytest.raises(ImageError):
        validate_image(path)


def test_reject_animation(tmp_path):
    path = tmp_path / "animated.webp"
    image = Image.new("RGB", (20, 20), "red")
    image.save(path, save_all=True, append_images=[Image.new("RGB", (20, 20), "blue")])
    with pytest.raises(ImageError, match="Animated"):
        validate_image(path)
