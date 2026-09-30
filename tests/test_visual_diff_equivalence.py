import hashlib
import random
from io import BytesIO

import pytest
from PIL import Image

from ai_workflow.visual_diff import compare_pixels


@pytest.mark.parametrize("tolerance", [0, 1, 8])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("mode", ["same", "near", "random", "alpha"])
def test_matches_scalar_pixel_definition(tmp_path, tolerance, masked, mode):
    rng = random.Random(742)  # noqa: S311 - deterministic test pixels
    width, height = 31, 23
    pixels = [tuple(rng.randrange(256) for _ in range(4)) for _ in range(width * height)]
    actual = []
    for pixel in pixels:
        if mode == "same":
            actual.append(pixel)
        elif mode == "near":
            actual.append(tuple(max(0, min(255, c + rng.randrange(-9, 10))) for c in pixel))
        elif mode == "alpha":
            actual.append((*pixel[:3], rng.randrange(256)))
        else:
            actual.append(tuple(rng.randrange(256) for _ in range(4)))
    paths = [tmp_path / "reference.png", tmp_path / "actual.png"]
    for path, data in zip(paths, [pixels, actual], strict=True):
        image = Image.new("RGBA", (width, height))
        image.putdata(data)
        image.save(path)
    masks = [{"x": 1, "y": 1, "width": 3, "height": 4}] if masked else []
    excluded = {y * width + x for y in range(1, 5) for x in range(1, 4)} if masked else set()
    diff = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    changed = []
    total = maximum = 0
    for index, (left, right) in enumerate(zip(pixels, actual, strict=True)):
        point = (index % width, index // width)
        if index in excluded:
            diff.putpixel(point, (0, 96, 255, 160))
            continue
        deltas = [abs(a - b) for a, b in zip(left, right, strict=True)]
        maximum = max(maximum, *deltas)
        total += sum(deltas)
        if max(deltas) > tolerance:
            changed.append(point)
            diff.putpixel(point, (255, 0, 0, 255))
    encoded = BytesIO()
    diff.save(encoded, format="PNG", optimize=False, compress_level=9)
    result = compare_pixels(*paths, channel_tolerance=tolerance, masks=masks)
    compared = width * height - len(excluded)
    assert result["diff_sha256"] == hashlib.sha256(encoded.getvalue()).hexdigest()
    assert result["different_pixels"] == len(changed)
    assert result["different_ratio"] == len(changed) / compared
    assert result["max_channel_delta"] == maximum
    assert result["mean_channel_delta"] == total / (compared * 4)
    assert result["masked_pixels"] == len(excluded)
    assert result["compared_pixels"] == compared
    expected = None
    if changed:
        xs, ys = zip(*changed, strict=True)
        expected = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    assert result["difference_bbox"] == expected
    assert result["passed"] is (not changed)
