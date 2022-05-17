import shutil
from pathlib import Path

import pytest

from panimg import convert
from tests import RESOURCE_PATH


@pytest.mark.parametrize("post_processors", (None, []))
def test_dzi_creation(tmpdir_factory, post_processors):
    filenames = [
        "valid_tiff.tif",
        "no_dzi.tif",
        "invalid_resolutions_tiff.tif",
    ]

    input_dir = Path(tmpdir_factory.mktemp("input"))
    output_dir = Path(tmpdir_factory.mktemp("output"))

    for f in filenames:
        shutil.copy(RESOURCE_PATH / f, input_dir / f)

    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        post_processors=post_processors,
    )

    assert len(result.new_images) == 2

    if post_processors is None:
        assert len(result.new_image_files) == 3
        assert len(result.new_folders) == 1
    else:
        assert len(result.new_image_files) == 2
        assert len(result.new_folders) == 0
