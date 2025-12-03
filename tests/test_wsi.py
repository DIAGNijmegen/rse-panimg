from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from panimg.image_builders import image_builder_dicom, image_builder_tiff
from panimg.models import ColorSpace, EyeChoice
from panimg.panimg import _build_files
from tests import RESOURCE_PATH

DEFAULT_EXPECTED_IMAGE_PROPERTIES = {
    "width": 154,
    "height": 290,
    "voxel_width_mm": 0.125,
    "voxel_height_mm": 0.125,
    "resolution_levels": 1,
    "depth": 1,
    "voxel_depth_mm": None,
    "timepoints": None,
    "window_center": None,
    "window_width": None,
    "color_space": ColorSpace.YCBCR,
    "eye_choice": EyeChoice.NOT_APPLICABLE,
    "segments": None,
}


@pytest.mark.parametrize(
    "src,expected_image,errors",
    (
        (
            RESOURCE_PATH / "dicom_wsi/sparse_with_bot",
            DEFAULT_EXPECTED_IMAGE_PROPERTIES,
            0,
        ),
        (
            RESOURCE_PATH / "dicom_wsi/sparse_no_bot",
            DEFAULT_EXPECTED_IMAGE_PROPERTIES,
            0,
        ),
        (
            RESOURCE_PATH / "dicom_wsi/full_with_bot",
            DEFAULT_EXPECTED_IMAGE_PROPERTIES,
            0,
        ),
        (
            RESOURCE_PATH / "dicom_wsi/full_no_bot",
            DEFAULT_EXPECTED_IMAGE_PROPERTIES,
            0,
        ),
        (RESOURCE_PATH / "dicom_wsi/non_wsi_dcm", {}, 1),
        (RESOURCE_PATH / "isyntax_wsi", {}, 0),
    ),
)
def test_image_builder_wsi(
    src: Path, expected_image: dict[str, Any], errors: int
):
    files = {f for f in src.rglob("*") if f.is_file()}
    if not files and src.name == "isyntax_wsi":
        pytest.xfail(
            reason="iSyntax resource is not available. "
            "To run this test, download the file using --download-files."
        )
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_tiff,
            files=files,
            output_directory=Path(output),
        )

    assert len(result.file_errors) == errors
    if errors == 0:
        assert result.consumed_files == files
        assert len(result.new_images) == 1
        for res in result.new_images:
            for k, v in expected_image.items():
                assert getattr(res, k) == v


def test_dicom_wsi_fails_for_dicom_builder(tmpdir):
    src = RESOURCE_PATH / "dicom_wsi/sparse_with_bot"
    files = {f for f in src.rglob("*") if f.is_file()}
    result = _build_files(
        builder=image_builder_dicom, files=files, output_directory=tmpdir
    )

    assert len(result.new_image_files) == 0
    assert len(result.file_errors) == 1
