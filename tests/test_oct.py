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
        RESOURCE_PATH / "oct/eg_oct_fds.fds",
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
            assert result.width in (768, 2048)
            assert result.height in (768, 1536)
            assert result.depth is None
            assert result.voxel_width_mm is None
            assert result.voxel_height_mm is None
            assert result.voxel_depth_mm is None
            assert result.eye_choice is not None
        else:
            assert result.width == 512
            assert result.height in (650, 496)
            assert result.depth in (128, 49)
            assert result.voxel_width_mm in (0.046875, 0.12244897959183673)
            assert result.voxel_height_mm in (0.0035, 0.0039)
            assert result.voxel_depth_mm in (0.01171875, 0.0087890625)
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
