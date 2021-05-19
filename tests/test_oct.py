import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from panimg.image_builders.oct import (
    format_error,
    image_builder_oct,
)
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "src,expected_oct_properties",
    (
        # TODO retrieve publicly usable E2E file and minimize it
        # RESOURCE_PATH / "oct/BRVO_O4003_baseline.e2e",
        (
            # Minimized .fda OCT file was created by taking example OCT file at
            # biobank.ndph.ox.ac.uk/showcase/showcase/examples/eg_oct_fda.fda
            # and downsizing:
            #   - OCT volume (@IMG_JPEG) to 512x650x1 J2C encoded,
            #   - Fundus (@IMG_FUNDUS) to 2x3x1 J2C encoded
            RESOURCE_PATH / "oct/fda_minimized.fda",
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
                "depth": 4,
                "voxel_width_mm": 3.0,
                "voxel_height_mm": 0.0035,
                "voxel_depth_mm": 1.5,
                "eye_choice": "U",
            },
        ),
    ),
)
def test_image_builder_oct(tmpdir, src, expected_oct_properties):
    dest = Path(tmpdir) / src.name
    shutil.copy(str(src), str(dest))
    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_oct, files=files, output_directory=output,
        )

    assert result.consumed_files == {dest}
    assert len(result.new_images) == 1
    for result in result.new_images:
        expected_values = expected_oct_properties
        for k, v in expected_values.items():
            assert getattr(result, k) == v


def test_image_builder_oct_corrupt_file(tmpdir):
    src = RESOURCE_PATH / "oct/corrupt.fds"
    dest = Path(tmpdir) / src.name
    shutil.copy(str(src), str(dest))

    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_oct, files=files, output_directory=output,
        )

    assert result.file_errors == {
        dest: [
            format_error(
                "Not a valid OCT file " "(supported formats: .fds,.fda,.e2e)"
            )
        ],
    }
    assert result.consumed_files == set()
