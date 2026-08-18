import json
from pathlib import Path

import pytest
from PIL import Image

from ai_workflow.cli import main
from ai_workflow.visual_diff import compare_pixels


def _image(path: Path, size: tuple[int, int] = (10, 10)) -> None:
    Image.new("RGBA", size, (10, 20, 30, 255)).save(path)


def test_identical_images_compare_every_pixel_and_write_deterministic_diff(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    difference = tmp_path / "diff.png"
    _image(reference)
    _image(actual)

    metrics = compare_pixels(reference, actual, diff_path=difference)

    assert metrics["passed"] is True
    assert metrics["compared_pixels"] == 100
    assert metrics["different_pixels"] == 0
    assert metrics["difference_bbox"] is None
    assert difference.is_file()


def test_one_changed_pixel_fails_strict_comparison(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    _image(reference)
    _image(actual)
    with Image.open(actual) as source:
        changed = source.convert("RGBA")
    changed.putpixel((3, 4), (11, 20, 30, 255))
    changed.save(actual)

    metrics = compare_pixels(reference, actual)

    assert metrics["passed"] is False
    assert metrics["different_pixels"] == 1
    assert metrics["different_ratio"] == 0.01
    assert metrics["difference_bbox"] == [3, 4, 4, 5]


def test_bounded_tolerance_and_mask_are_applied(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    _image(reference, (20, 20))
    _image(actual, (20, 20))
    with Image.open(actual) as source:
        changed = source.convert("RGBA")
    changed.putpixel((0, 0), (18, 20, 30, 255))
    changed.putpixel((1, 0), (255, 20, 30, 255))
    changed.save(actual)

    metrics = compare_pixels(
        reference,
        actual,
        channel_tolerance=8,
        masks=[{"x": 1, "y": 0, "width": 1, "height": 1, "reason": "native clock"}],
    )

    assert metrics["passed"] is True
    assert metrics["masked_pixels"] == 1
    assert metrics["different_pixels"] == 0
    assert metrics["max_channel_delta"] == 8


def test_dimension_mismatch_and_excessive_mask_are_rejected(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    _image(reference, (10, 10))
    _image(actual, (11, 10))
    with pytest.raises(RuntimeError, match="identical dimensions"):
        compare_pixels(reference, actual)

    _image(actual, (10, 10))
    with pytest.raises(RuntimeError, match="masked pixel ratio"):
        compare_pixels(
            reference,
            actual,
            masks=[{"x": 0, "y": 0, "width": 3, "height": 2, "reason": "too broad"}],
        )


def test_pixel_metrics_are_json_serializable(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    _image(reference)
    _image(actual)
    assert json.loads(json.dumps(compare_pixels(reference, actual)))["passed"] is True


def test_compare_images_cli_writes_failed_evidence(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    actual = tmp_path / "actual.png"
    _image(reference)
    _image(actual)
    with Image.open(actual) as source:
        changed = source.convert("RGBA")
    changed.putpixel((0, 0), (255, 255, 255, 255))
    changed.save(actual)

    code = main(
        [
            "compare-images",
            "--project",
            str(tmp_path),
            "--reference",
            "reference.png",
            "--actual",
            "actual.png",
            "--diff",
            "diff.png",
            "--metrics",
            "metrics.json",
        ]
    )

    assert code == 2
    assert (tmp_path / "diff.png").is_file()
    assert json.loads((tmp_path / "metrics.json").read_text())["passed"] is False
