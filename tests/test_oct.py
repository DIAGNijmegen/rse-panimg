import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from panimg.image_builders.oct import format_error, image_builder_oct
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "src,expected_fundus_properties,expected_oct_properties",
    (
        (
            # Minimized .fda OCT file was created by taking example OCT file at
            # biobank.ndph.ox.ac.uk/showcase/showcase/examples/eg_oct_fda.fda
            # and downsizing:
            #   - OCT volume (@IMG_JPEG) to 512x650x1 J2C encoded,
            #   - Fundus (@IMG_FUNDUS) to 2x3x1 J2C encoded
            RESOURCE_PATH / "oct/fda_minimized.fda",
            {
                "width": 2,
                "height": 3,
                "depth": None,
                "voxel_width_mm": None,
                "voxel_height_mm": None,
                "voxel_depth_mm": None,
                "eye_choice": "U",
            },
            {
                "width": 512,
                "height": 650,
                "depth": 1,
                "voxel_width_mm": 0.01171875,
                "voxel_height_mm": 0.0035,
                "voxel_depth_mm": 6,
                "eye_choice": "U",
            },
        ),
        (
            # Minimized .fds OCT file was created by taking example OCT file at
            # biobank.ndph.ox.ac.uk/showcase/showcase/examples/eg_oct_fds.fds
            # and downsizing:
            #   - OCT volume (@IMG_SCAN_03) to 2x3x4 16bit voxels,
            #   - OBS (@IMG_OBS) scan to 2x3x1 24bit voxels,
            #   - MOT_COMP (@IMG_MOT_COMP_03) to 2x3x4 16bit voxels,
            #   - TRC (@IMG_TRC_02) to 2x3x4 24bit voxels
            RESOURCE_PATH / "oct/fds_minimized.fds",
            {
                "width": 2,
                "height": 3,
                "depth": None,
                "voxel_width_mm": None,
                "voxel_height_mm": None,
                "voxel_depth_mm": None,
                "eye_choice": "U",
            },
            {
                "width": 2,
                "height": 3,
                "depth": 4,
                "voxel_width_mm": 3.0,
                "voxel_height_mm": 0.0035,
                "voxel_depth_mm": 1.5,
                "eye_choice": "U",
            },
        ),
        (
            # Minimized .e2e OCT file was created by taking example OCT file from RUMC
            # and downsizing:
            #   - OCT volume (chunk type = 1073741824, chunk ind = 1) to 512x496x1
            #   - Fundus image (chunk type = 1073741824, chunk ind = 0) to 2x3x1
            #   - deleting all MDbData chunks other than the OCT slice, the fundus
            #     image and the laterality information (chunk type = 11)
            RESOURCE_PATH / "oct/e2e_minimized.E2E",
            {
                "width": 2,
                "height": 3,
                "depth": None,
                "voxel_width_mm": None,
                "voxel_height_mm": None,
                "voxel_depth_mm": None,
                "eye_choice": "U",
            },
            {
                "width": 512,
                "height": 496,
                "depth": 1,
                "voxel_width_mm": 0.01171875,
                "voxel_height_mm": 0.0039,
                "voxel_depth_mm": 4.5,
                "eye_choice": "U",
            },
        ),
    ),
)
def test_image_builder_oct(
    tmpdir, src, expected_fundus_properties, expected_oct_properties
):
    dest = Path(tmpdir) / src.name
    shutil.copy(str(src), str(dest))
    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_oct, files=files, output_directory=output
        )

    assert result.consumed_files == {dest}
    assert len(result.new_images) == 1
    for res in result.new_images:
        expected_values = expected_oct_properties
        if "fundus" in res.name:
            # expected_values = expected_fundus_properties
            continue  # Skip fundus_images for now

        for k, v in expected_values.items():
            assert getattr(res, k) == v


def test_image_builder_oct_corrupt_file(tmpdir):
    src = RESOURCE_PATH / "oct/corrupt.fds"
    dest = Path(tmpdir) / src.name
    shutil.copy(str(src), str(dest))

    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_oct, files=files, output_directory=output
        )

    assert result.file_errors == {
        dest: [
            format_error(
                "Not a valid OCT file " "(supported formats: .fds,.fda,.e2e)"
            )
        ]
    }
    assert result.consumed_files == set()
