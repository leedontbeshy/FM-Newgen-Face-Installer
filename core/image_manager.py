"""Validate, preview and stage full-size PNG images without touching targets."""

import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from core.filesystem import copy_durable, flush_file, temporary_path

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}


class ImageError(ValueError):
    pass


def load_image(path: str | Path) -> Image.Image:
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageError("Select a PNG, JPG, JPEG or WEBP image.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as source:
                if source.format not in SUPPORTED_FORMATS:
                    raise ImageError("The file is not a supported PNG, JPEG or WEBP image.")
                if getattr(source, "n_frames", 1) > 1:
                    raise ImageError("Animated images are unsupported. Select a still image.")
                source.verify()
            with Image.open(path) as source:
                source.load()
                result = source.copy()
                result.format = source.format
                return result
    except (
        OSError,
        UnidentifiedImageError,
        SyntaxError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise ImageError(f"Could not read this image: {error}") from error


def validate_image(path: str | Path) -> None:
    with load_image(path):
        pass


def preview_image(path: str | Path, size=(240, 240)) -> tuple[Image.Image, tuple[int, int]]:
    with load_image(path) as source:
        full_size = source.size
        preview = ImageOps.exif_transpose(source).convert("RGBA")
        preview.thumbnail(size, Image.Resampling.LANCZOS)
        return preview, full_size


def stage_png(source: str | Path, folder: Path) -> Path:
    """Return a durable temporary PNG; caller owns cleanup and atomic rename."""
    source = Path(source)
    image = load_image(source)
    temporary = temporary_path(folder, ".png.tmp")
    try:
        with image:
            if image.format == "PNG":
                # Preserves palette, transparency, bit depth and metadata exactly.
                copy_durable(source, temporary)
            else:
                converted = ImageOps.exif_transpose(image)
                converted = converted.convert(
                    "RGBA" if "A" in converted.getbands() or "transparency" in converted.info else "RGB"
                )
                options = {}
                if image.info.get("icc_profile"):
                    options["icc_profile"] = image.info["icc_profile"]
                with converted, temporary.open("wb") as stream:
                    converted.save(stream, format="PNG", **options)
                    flush_file(stream)
        with Image.open(temporary) as check:
            if check.format != "PNG":
                raise ImageError("PNG conversion failed.")
            check.verify()
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
