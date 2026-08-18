"""Deterministic pixel-by-pixel comparison for design-fidelity evidence."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_CHANNEL_TOLERANCE = 8
MAX_CHANGED_RATIO = 0.001
MAX_MASKED_RATIO = 0.05
MAX_IMAGE_PIXELS = 50_000_000
MAX_DIMENSION = 10_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unsafe_dimensions(width: int, height: int) -> bool:
    return (
        width <= 0
        or height <= 0
        or width > MAX_DIMENSION
        or height > MAX_DIMENSION
        or width * height > MAX_IMAGE_PIXELS
    )


def _rgba(path: Path) -> Image.Image:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"comparison image is missing or empty: {path}")
    try:
        with Image.open(path) as source:
            width, height = source.size
            if _unsafe_dimensions(width, height):
                raise RuntimeError(
                    f"comparison image dimensions are unsafe: {path} ({width}x{height})"
                )
            source.load()
            image = source.convert("RGBA")
    except (UnidentifiedImageError, OSError) as error:
        raise RuntimeError(f"comparison image cannot be decoded: {path}") from error
    width, height = image.size
    if _unsafe_dimensions(width, height):
        raise RuntimeError(f"comparison image dimensions are unsafe: {path} ({width}x{height})")
    return image


def _mask_map(
    width: int, height: int, masks: list[dict[str, Any]]
) -> tuple[bytearray, int]:
    masked = bytearray(width * height)
    for mask in masks:
        try:
            x = int(mask["x"])
            y = int(mask["y"])
            mask_width = int(mask["width"])
            mask_height = int(mask["height"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("pixel mask requires integer x, y, width, and height") from error
        if (
            x < 0
            or y < 0
            or mask_width <= 0
            or mask_height <= 0
            or x + mask_width > width
            or y + mask_height > height
        ):
            raise RuntimeError(f"pixel mask escapes {width}x{height}: {mask}")
        for row in range(y, y + mask_height):
            start = row * width + x
            masked[start : start + mask_width] = b"\x01" * mask_width
    count = sum(masked)
    if count / (width * height) > MAX_MASKED_RATIO:
        raise RuntimeError(
            f"masked pixel ratio exceeds {MAX_MASKED_RATIO:.3f}: {count / (width * height):.6f}"
        )
    return masked, count


def _diff_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def compare_pixels(
    reference_path: Path,
    actual_path: Path,
    *,
    diff_path: Path | None = None,
    channel_tolerance: int = 0,
    max_changed_ratio: float = 0.0,
    masks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare every unmasked RGBA pixel and return reproducible numeric evidence."""
    if not 0 <= channel_tolerance <= MAX_CHANNEL_TOLERANCE:
        raise RuntimeError(
            f"channel tolerance must be between 0 and {MAX_CHANNEL_TOLERANCE}"
        )
    if not 0 <= max_changed_ratio <= MAX_CHANGED_RATIO:
        raise RuntimeError(
            f"changed-pixel threshold must be between 0 and {MAX_CHANGED_RATIO}"
        )
    reference = _rgba(reference_path)
    actual = _rgba(actual_path)
    if reference.size != actual.size:
        raise RuntimeError(
            "pixel comparison requires identical dimensions: "
            f"reference={reference.size[0]}x{reference.size[1]}, "
            f"actual={actual.size[0]}x{actual.size[1]}"
        )
    width, height = reference.size
    mask_map, masked_pixels = _mask_map(width, height, masks or [])
    compared_pixels = width * height - masked_pixels
    if compared_pixels <= 0:
        raise RuntimeError("pixel comparison has no unmasked pixels")

    reference_bytes = memoryview(reference.tobytes())
    actual_bytes = memoryview(actual.tobytes())
    difference = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    difference_pixels = difference.load()
    assert difference_pixels is not None
    different_pixels = 0
    maximum_delta = 0
    total_delta = 0
    minimum_x = width
    minimum_y = height
    maximum_x = -1
    maximum_y = -1
    for index in range(width * height):
        x = index % width
        y = index // width
        if mask_map[index]:
            difference_pixels[x, y] = (0, 96, 255, 160)
            continue
        offset = index * 4
        deltas = tuple(
            abs(reference_bytes[offset + channel] - actual_bytes[offset + channel])
            for channel in range(4)
        )
        pixel_delta = max(deltas)
        maximum_delta = max(maximum_delta, pixel_delta)
        total_delta += sum(deltas)
        if pixel_delta > channel_tolerance:
            different_pixels += 1
            minimum_x = min(minimum_x, x)
            minimum_y = min(minimum_y, y)
            maximum_x = max(maximum_x, x)
            maximum_y = max(maximum_y, y)
            difference_pixels[x, y] = (255, 0, 0, 255)
    changed_ratio = different_pixels / compared_pixels
    difference_bbox = (
        None
        if different_pixels == 0
        else [minimum_x, minimum_y, maximum_x + 1, maximum_y + 1]
    )
    difference_bytes = _diff_png(difference)
    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_bytes(difference_bytes)
    return {
        "version": 1,
        "algorithm": "rgba-max-channel-v1",
        "reference_sha256": _sha256(reference_path),
        "actual_sha256": _sha256(actual_path),
        "diff_sha256": hashlib.sha256(difference_bytes).hexdigest(),
        "width": width,
        "height": height,
        "total_pixels": width * height,
        "masked_pixels": masked_pixels,
        "compared_pixels": compared_pixels,
        "different_pixels": different_pixels,
        "different_ratio": changed_ratio,
        "max_channel_delta": maximum_delta,
        "mean_channel_delta": total_delta / (compared_pixels * 4),
        "difference_bbox": difference_bbox,
        "channel_tolerance": channel_tolerance,
        "max_changed_ratio": max_changed_ratio,
        "passed": changed_ratio <= max_changed_ratio,
    }


def parse_mask(value: str) -> dict[str, int | str]:
    """Parse one CLI mask in x,y,width,height,reason form."""
    parts = [part.strip() for part in value.split(",", 4)]
    if len(parts) != 5 or not parts[4]:
        raise RuntimeError("--mask must use x,y,width,height,reason")
    try:
        x, y, width, height = (int(part) for part in parts[:4])
    except ValueError as error:
        raise RuntimeError("--mask coordinates must be integers") from error
    return {"x": x, "y": y, "width": width, "height": height, "reason": parts[4]}
