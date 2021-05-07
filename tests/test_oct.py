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
    "src",
    (
        # RESOURCE_PATH / "oct/BRVO_O4003_baseline.e2e",
        RESOURCE_PATH / "oct/eg_oct_fda.fda",
        # Minimized .fds OCT file was created by taking example OCT file at
        # biobank.ndph.ox.ac.uk/showcase/showcase/examples/eg_oct_fds.fds
        # and downsizing:
        #   - OCT volume (@IMG_SCAN_03) to 2x2x2 16bit voxels,
        #   - OBS (@IMG_OBS) scan to 2x2x1 24bit voxels,
        #   - MOT_COMP (@IMG_MOT_COMP_03) to 2x2x2 16bit voxels,
        #   - TRC (@IMG_TRC_02) to 2x2x2 24bit voxels
        RESOURCE_PATH / "oct/fds_minimized.fds",
    ),
)
def test_image_builder_oct(tmpdir, src):
    dest = Path(tmpdir) / src.name
    shutil.copy(str(src), str(dest))
    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_oct, files=files, output_directory=output,
        )

    assert result.consumed_files == {dest}
    assert len(result.new_images) == 2
    for result in result.new_images:
        if "fundus" in result.name:
            assert result.width in (2048, 2, 768)
            assert result.height in (1536, 2, 768)
            assert result.depth is None
            assert result.voxel_width_mm is None
            assert result.voxel_height_mm is None
            assert result.voxel_depth_mm is None
            assert result.eye_choice is not None
        else:
            assert result.width in (2, 512)
            assert result.height in (2, 650, 496)
            assert result.depth in (2, 128, 49)
            assert result.voxel_width_mm in (
                3,
                0.12244897959183673,
                0.01171875,
            )
            assert result.voxel_height_mm in (0.0035, 0.0039)
            assert result.voxel_depth_mm in (3, 0.09183673469387756, 0.046875)
            assert result.eye_choice is not None


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
