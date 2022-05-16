import shutil
from pathlib import Path

import numpy as np
import pytest
from SimpleITK import SimpleITK

from panimg import convert
from panimg.post_processors.mha_pixel_range import (
    MAXIMUM_VALUE_TAG,
    MINIMUM_VALUE_TAG,
)
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


@pytest.mark.parametrize(
    "post_processors,image_files,minimum_pixel_value,maximum_pixel_value",
    [
        (  # No post processors
            [],
            ["image_min10_max10.mha"],
            None,
            None,
        ),
        (  # Default post processors
            None,
            ["image_min10_max10.mha"],
            -10,
            10,
        ),
        (  # Predefined ranges in input file
            None,
            [
                "image3x4-extra-stuff.mhd",
                "image3x4.zraw",
            ],
            -100,
            100,
        ),
        (  # 3D image
            None,
            ["image10x10x10.mha"],
            8.341e-05,
            0.99918,
        ),
        (  # 4D image
            None,
            ["image10x11x12x13.mha"],
            0,
            0,
        ),
    ],
)
def test_mha_value_range(
    tmpdir_factory,
    post_processors,
    image_files,
    minimum_pixel_value,
    maximum_pixel_value,
):
    input_dir = Path(tmpdir_factory.mktemp("input"))
    output_dir = Path(tmpdir_factory.mktemp("output"))

    for file in image_files:
        shutil.copy(RESOURCE_PATH / file, input_dir / file)

    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        post_processors=post_processors,
    )

    assert len(result.new_image_files) == 1  # Sanity check

    result_image = list(result.new_image_files)[0]
    reader = SimpleITK.ImageFileReader()
    reader.SetFileName(str(result_image.file))
    reader.ReadImageInformation()

    for value, tag in [
        (maximum_pixel_value, MAXIMUM_VALUE_TAG),
        (minimum_pixel_value, MINIMUM_VALUE_TAG),
    ]:
        if value is None:
            assert not reader.HasMetaDataKey(tag)
        else:
            assert np.isclose(float(reader.GetMetaData(tag)), value)
