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
    assert len(result.new_images) == 1
    image = result.new_images.pop()
    assert image.width == 512
    assert image.height in (650, 496)
    assert image.depth in (128, 49)


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
